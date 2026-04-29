from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import jsonschema
from lathe.scene.planner import (
    compare_scene_plan_asset_reuse,
    get_scene_plan_schema,
    plan_scene,
    validate_scene_plan_payload,
)
from lathe.wonder import generate_scene_plan

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = REPO_ROOT / "examples" / "wonder" / "alchemist_observatory"
EXAMPLE_BRIEF = EXAMPLE_DIR / "dream_brief.json"
EXAMPLE_SCENE = EXAMPLE_DIR / "scene_graph.json"


def _example_brief() -> dict:
    return json.loads(EXAMPLE_BRIEF.read_text(encoding="utf-8"))


def _example_scene() -> dict:
    return json.loads(EXAMPLE_SCENE.read_text(encoding="utf-8"))


def _transform(x: float) -> dict:
    return {
        "position": [x, 0, 0],
        "rotation": [0, 0, 0],
        "scale": [1, 1, 1],
    }


def _object(
    object_id: str,
    lathe_asset: str,
    *,
    source_family: str | None = None,
    variant: str | None = None,
    x: float = 0,
    state: dict | None = None,
    surface_overrides: dict | None = None,
    affordances: list[dict] | None = None,
) -> dict:
    payload = {
        "object_id": object_id,
        "name": object_id.replace("obj_", "").replace("_", " ").title(),
        "role": "dressing_prop",
        "region": "region_main",
        "lathe_asset": lathe_asset,
        "transform": _transform(x),
        "material_bindings": [{"slot": "body", "material": "mat_wax_001"}],
        "semantic_tags": ["test"],
        "state": state or {"lit": True},
        "surface_overrides": surface_overrides or {},
        "affordances": affordances or [],
    }
    if source_family is not None:
        payload["source_family"] = source_family
    if variant is not None:
        payload["variant"] = variant
    return payload


def _scene(objects: list[dict]) -> dict:
    return {
        "schema_version": "lathe.scene_graph.v1",
        "scene_id": "test_scene",
        "version": 1,
        "prompt": "Test scene.",
        "style_bible": {
            "mood": ["quiet"],
            "palette": ["warm"],
            "materials": ["wax"],
            "forms": ["simple"],
            "lighting": ["soft"],
        },
        "regions": [
            {
                "region_id": "region_main",
                "name": "Main",
                "type": "interior",
                "purpose": "Test",
                "mood": "quiet",
                "bounds": {"center": [0, 0, 0], "size": [8, 8, 4]},
            }
        ],
        "objects": objects,
        "relationships": [],
        "materials": [{"material_id": "mat_wax_001", "name": "Wax", "role": "wax"}],
        "lights": [],
        "cameras": [
            {
                "camera_id": "camera_main",
                "target": objects[0]["object_id"],
                "framing": "inspection",
                "purpose": "Inspect",
                "transform": _transform(-4),
            }
        ],
        "curiosity_anchors": [],
        "hidden_state": [],
        "exports": [{"target": "glb", "format": "glb", "path": "dist/test_scene.glb"}],
        "build_artifacts": [],
        "memory_events": [],
    }


def _codes(plan: dict) -> list[str]:
    return [diagnostic["code"] for diagnostic in plan["diagnostics"]]


def test_scene_plan_schema_is_valid_json_schema() -> None:
    jsonschema.Draft202012Validator.check_schema(get_scene_plan_schema())


def test_plan_scene_emits_deterministic_tasks_for_four_objects() -> None:
    objects = [
        _object("obj_table_001", "table_asset", source_family="tables", x=2),
        _object("obj_candle_002", "candle_asset", source_family="ritual_candles", x=1),
        _object("obj_arch_001", "arch_asset", source_family="arches", x=3),
        _object("obj_candle_001", "small_candle_asset", source_family="ritual_candles", x=0),
    ]

    plan = plan_scene(_scene(objects), mode="preview")

    assert validate_scene_plan_payload(plan) == []
    assert plan["scene_id"] == "test_scene"
    assert plan["mode"] == "preview"
    assert plan["metadata"]["counts"]["objects"] == 4
    assert len(plan["asset_tasks"]) == 4
    assert len(plan["assembly_tasks"]) == 4
    assert [task["object_id"] for task in plan["assembly_tasks"]] == [
        "obj_arch_001",
        "obj_candle_001",
        "obj_candle_002",
        "obj_table_001",
    ]
    assert plan["diagnostics"] == []
    assert plan["warnings"] == []


def test_repeated_candle_instances_share_one_cached_asset() -> None:
    objects = [
        _object("obj_candle_002", "candle_cluster", source_family="ritual_candles", variant="melted", x=2),
        _object("obj_candle_001", "candle_cluster", source_family="ritual_candles", variant="melted", x=-2),
    ]

    plan = plan_scene(_scene(objects), mode="preview")

    candle_tasks = [
        task for task in plan["asset_tasks"] if task["source"]["lathe_asset"] == "candle_cluster"
    ]
    assert len(candle_tasks) == 1
    assert candle_tasks[0]["object_ids"] == ["obj_candle_001", "obj_candle_002"]
    assert candle_tasks[0]["requires_unique_build"] is False
    assert len({task["cache_key"] for task in plan["assembly_tasks"]}) == 1
    assert plan["cache_keys"][0]["shareable"] is True


def test_branch_plan_reuses_unchanged_asset_builds() -> None:
    base_scene = _scene(
        [
            _object("obj_candle_001", "candle_cluster", source_family="ritual_candles", x=-1),
            _object("obj_arch_001", "rib_arch", source_family="bone_arches", x=2),
        ]
    )
    branch_scene = deepcopy(base_scene)
    branch_scene["version"] = 2
    branch_scene["objects"][0]["transform"] = _transform(-2)
    branch_scene["objects"][1]["name"] = "Reframed Rib Arch"
    branch_scene["objects"].append(
        _object("obj_lens_001", "sealed_lens", source_family="black_glass_relics", x=0)
    )

    base_plan = plan_scene(base_scene, mode="preview")
    branch_plan = plan_scene(branch_scene, mode="preview", reuse_from_plan=base_plan)

    assert validate_scene_plan_payload(branch_plan) == []
    reuse = branch_plan["branch_reuse"]
    assert reuse == compare_scene_plan_asset_reuse(base_plan, branch_plan)
    assert reuse["summary"] == {
        "base_asset_tasks": 2,
        "branch_asset_tasks": 3,
        "reusable_asset_tasks": 2,
        "new_asset_tasks": 1,
        "skipped_asset_tasks": 0,
        "base_only_asset_tasks": 0,
        "reuse_ratio": 0.6667,
    }
    assert {entry["status"] for entry in reuse["reusable_asset_tasks"]} == {"reusable_asset_build"}
    assert {entry["branch_object_ids"][0] for entry in reuse["reusable_asset_tasks"]} == {
        "obj_arch_001",
        "obj_candle_001",
    }
    assert reuse["new_asset_tasks"][0]["branch_object_ids"] == ["obj_lens_001"]
    assert reuse["diagnostics"] == []


def test_branch_plan_does_not_reuse_changed_asset_overrides() -> None:
    base_scene = _scene(
        [_object("obj_candle_001", "candle_cluster", source_family="ritual_candles", state={"lit": True})]
    )
    branch_scene = deepcopy(base_scene)
    branch_scene["version"] = 2
    branch_scene["objects"][0]["state"] = {"lit": True, "wax_drip_amount": 0.8}

    base_plan = plan_scene(base_scene, mode="preview")
    branch_plan = plan_scene(branch_scene, mode="preview", reuse_from_plan=base_plan)

    assert validate_scene_plan_payload(branch_plan) == []
    reuse = branch_plan["branch_reuse"]
    assert reuse["summary"]["reusable_asset_tasks"] == 0
    assert reuse["summary"]["new_asset_tasks"] == 1
    assert reuse["summary"]["base_only_asset_tasks"] == 1
    assert reuse["new_asset_tasks"][0]["status"] == "new_asset_build"
    assert reuse["base_only_asset_tasks"][0]["status"] == "base_only_asset_build"
    assert reuse["new_asset_tasks"][0]["cache_key"] != reuse["base_only_asset_tasks"][0]["cache_key"]


def test_branch_plan_does_not_reuse_changed_source_signature() -> None:
    base_scene = _scene(
        [_object("obj_candle_001", "candle_cluster", source_family="ritual_candles", state={"lit": True})]
    )
    branch_scene = deepcopy(base_scene)
    branch_scene["version"] = 2
    branch_scene["objects"][0]["source_family"] = "ghost_candles"

    base_plan = plan_scene(base_scene, mode="preview")
    branch_plan = plan_scene(branch_scene, mode="preview", reuse_from_plan=base_plan)

    assert validate_scene_plan_payload(branch_plan) == []
    reuse = branch_plan["branch_reuse"]
    assert reuse["summary"]["reusable_asset_tasks"] == 0
    assert reuse["summary"]["new_asset_tasks"] == 1
    assert reuse["summary"]["base_only_asset_tasks"] == 1
    assert reuse["new_asset_tasks"][0]["cache_key"] != reuse["base_only_asset_tasks"][0]["cache_key"]


def test_branch_plan_reports_mode_mismatch_without_blocking_validation() -> None:
    scene_graph = _scene([_object("obj_candle_001", "candle_cluster", source_family="ritual_candles")])

    base_plan = plan_scene(scene_graph, mode="preview")
    branch_plan = plan_scene(deepcopy(scene_graph), mode="final", reuse_from_plan=base_plan)

    assert validate_scene_plan_payload(branch_plan) == []
    reuse = branch_plan["branch_reuse"]
    assert reuse["summary"]["reusable_asset_tasks"] == 0
    assert reuse["summary"]["new_asset_tasks"] == 1
    assert [diagnostic["code"] for diagnostic in reuse["diagnostics"]] == ["SP3101"]
    assert reuse["diagnostics"][0]["details"] == {"base_mode": "preview", "branch_mode": "final"}


def test_branch_reuse_schema_rejects_loose_contract_values() -> None:
    scene_graph = _scene([_object("obj_candle_001", "candle_cluster", source_family="ritual_candles")])
    base_plan = plan_scene(scene_graph, mode="preview")
    branch_plan = plan_scene(deepcopy(scene_graph), mode="preview", reuse_from_plan=base_plan)

    bad_mode = deepcopy(branch_plan)
    bad_mode["branch_reuse"]["mode"] = "debug"
    bad_task_id = deepcopy(branch_plan)
    bad_task_id["branch_reuse"]["reusable_asset_tasks"][0]["base_asset_task_id"] = "not a task id"
    bad_source = deepcopy(branch_plan)
    bad_source["branch_reuse"]["reusable_asset_tasks"][0]["source"] = {"unexpected": True}

    for payload in (bad_mode, bad_task_id, bad_source):
        assert "SCENE_PLAN_SCHEMA_VALIDATION" in [
            diagnostic["code"] for diagnostic in validate_scene_plan_payload(payload)
        ]


def test_scene_plan_validation_rejects_duplicate_cache_key_entries() -> None:
    plan = plan_scene(_scene([_object("obj_candle_001", "candle_cluster", source_family="ritual_candles")]))
    plan["cache_keys"].append(deepcopy(plan["cache_keys"][0]))

    diagnostics = validate_scene_plan_payload(plan)

    assert "SP3004" in [diagnostic["code"] for diagnostic in diagnostics]


def test_scene_plan_validation_rejects_mismatched_cache_key_entries() -> None:
    plan = plan_scene(_scene([_object("obj_candle_001", "candle_cluster", source_family="ritual_candles")]))
    plan["cache_keys"][0]["source"]["source_family"] = "ghost_candles"

    diagnostics = validate_scene_plan_payload(plan)

    assert "SP3006" in [diagnostic["code"] for diagnostic in diagnostics]


def test_scene_plan_validation_rejects_missing_cache_key_entries() -> None:
    plan = plan_scene(_scene([_object("obj_candle_001", "candle_cluster", source_family="ritual_candles")]))
    plan["cache_keys"] = []

    diagnostics = validate_scene_plan_payload(plan)

    assert "SP3007" in [diagnostic["code"] for diagnostic in diagnostics]


def test_per_instance_asset_overrides_create_unique_variant_tasks() -> None:
    objects = [
        _object(
            "obj_candle_001",
            "candle_cluster",
            source_family="ritual_candles",
            variant="melted",
            state={"lit": True, "wax_drip_amount": 0.8},
        ),
        _object(
            "obj_candle_002",
            "candle_cluster",
            source_family="ritual_candles",
            variant="melted",
            state={"lit": True, "wax_drip_amount": 0.2},
        ),
    ]

    plan = plan_scene(_scene(objects), mode="preview")

    candle_tasks = sorted(plan["asset_tasks"], key=lambda task: task["object_ids"][0])
    assert len(candle_tasks) == 2
    assert {task["object_ids"][0] for task in candle_tasks} == {"obj_candle_001", "obj_candle_002"}
    assert len({task["cache_key"] for task in candle_tasks}) == 2
    assert all(task["variant"] == "melted" for task in candle_tasks)
    assert all(task["requires_unique_build"] is True for task in candle_tasks)
    assert all("asset_overrides" in task["uniqueness_reasons"] for task in candle_tasks)


def test_surface_and_affordance_overrides_are_instance_only() -> None:
    objects = [
        _object(
            "obj_door_001",
            "sealed_archive_door",
            source_family="mechanical_doors",
            surface_overrides={"scratches": 0.8, "dust": "heavy"},
            affordances=[{"id": "affordance_inspect_door_001", "action": "inspect"}],
        ),
        _object(
            "obj_door_002",
            "sealed_archive_door",
            source_family="mechanical_doors",
            surface_overrides={"scratches": 0.2, "dust": "light"},
            affordances=[{"id": "affordance_open_door_002", "action": "open"}],
        ),
    ]

    plan = plan_scene(_scene(objects), mode="preview")

    assert validate_scene_plan_payload(plan) == []
    assert len(plan["asset_tasks"]) == 1
    assert plan["asset_tasks"][0]["object_ids"] == ["obj_door_001", "obj_door_002"]
    assert plan["asset_tasks"][0]["requires_unique_build"] is False
    assert "surface_overrides" not in plan["asset_tasks"][0]["asset_overrides"]
    assert "affordances" not in plan["asset_tasks"][0]["asset_overrides"]
    by_object_id = {task["object_id"]: task for task in plan["assembly_tasks"]}
    assert by_object_id["obj_door_001"]["instance_overrides"]["surface_overrides"]["dust"] == "heavy"
    assert by_object_id["obj_door_002"]["instance_overrides"]["affordances"][0]["action"] == "open"


def test_missing_asset_reference_reports_diagnostic_and_generated_fallback() -> None:
    missing_source_object = _object("obj_unresolved_001", "placeholder")
    missing_source_object.pop("lathe_asset")
    scene_graph = _scene([missing_source_object])

    plan = plan_scene(scene_graph, mode="preview")

    assert "SP1001" in _codes(plan)
    diagnostic = next(item for item in plan["diagnostics"] if item["code"] == "SP1001")
    assert diagnostic["name"] == "missing_object_source_reference"
    assert diagnostic["path"] == "/objects/0"
    assert plan["asset_tasks"][0]["source"]["kind"] == "generated_fallback"
    assert plan["asset_tasks"][0]["source"]["generated"] is True
    assert plan["asset_tasks"][0]["requires_unique_build"] is True
    assert validate_scene_plan_payload(plan) == []


def test_preview_and_final_modes_have_distinct_budgets_and_render_plans() -> None:
    scene_graph = _scene([_object("obj_candle_001", "candle_cluster", source_family="ritual_candles")])

    preview = plan_scene(deepcopy(scene_graph), mode="preview")
    final = plan_scene(deepcopy(scene_graph), mode="final")

    assert preview["metadata"]["budgets"]["quality"] == "preview"
    assert final["metadata"]["budgets"]["quality"] == "final"
    assert preview["metadata"]["budgets"]["max_complexity"] < final["metadata"]["budgets"]["max_complexity"]
    assert preview["render_tasks"][0]["resolution"] == [1280, 720]
    assert final["render_tasks"][0]["resolution"] == [2048, 1152]
    assert final["render_tasks"][0]["passes"] != preview["render_tasks"][0]["passes"]


def test_long_object_and_camera_ids_produce_unique_task_ids() -> None:
    prefix = "obj_" + ("a" * 72)
    objects = [
        _object(prefix + "111", "shared_asset", source_family="shared_family", x=0),
        _object(prefix + "222", "shared_asset", source_family="shared_family", x=1),
    ]
    scene_graph = _scene(objects)
    camera_prefix = "camera_" + ("b" * 72)
    scene_graph["cameras"] = [
        {
            "camera_id": camera_prefix + "111",
            "target": objects[0]["object_id"],
            "framing": "inspection",
            "purpose": "Inspect first.",
            "transform": _transform(-4),
        },
        {
            "camera_id": camera_prefix + "222",
            "target": objects[1]["object_id"],
            "framing": "inspection",
            "purpose": "Inspect second.",
            "transform": _transform(-5),
        },
    ]

    plan = plan_scene(scene_graph, mode="preview")
    assembly_task_ids = [task["task_id"] for task in plan["assembly_tasks"]]
    render_task_ids = [task["task_id"] for task in plan["render_tasks"]]

    assert len(set(assembly_task_ids)) == 2
    assert len(set(render_task_ids)) == 3
    assert any(task_id.startswith("render_task_camera_topdown_debug_") for task_id in render_task_ids)
    assert validate_scene_plan_payload(plan) == []


def test_scene_plan_validation_reports_duplicate_task_ids() -> None:
    plan = plan_scene(_scene([_object("obj_candle_001", "candle_cluster", source_family="ritual_candles")]))
    plan["render_tasks"].append(deepcopy(plan["render_tasks"][0]))

    diagnostics = validate_scene_plan_payload(plan)

    assert "SP3001" in [diagnostic["code"] for diagnostic in diagnostics]


def test_generate_scene_plan_from_brief_and_scene_graph_is_deterministic() -> None:
    brief = _example_brief()
    scene_graph = _example_scene()

    first = generate_scene_plan(brief, scene_graph=scene_graph)
    second = generate_scene_plan(deepcopy(brief), scene_graph=deepcopy(scene_graph))

    assert first == second
    assert validate_scene_plan_payload(first) == []
    assert first["schema_version"] == "lathe.scene_plan.v1"
    assert first["plan_id"].startswith("plan_alchemist_observatory_")
    assert first["source_brief_id"] == "alchemist_observatory"
    assert first["source_prompt"] == brief["source_prompt"]


def test_generate_scene_plan_derives_render_tasks_from_scene_graph_cameras() -> None:
    plan = generate_scene_plan(_example_brief(), scene_graph=_example_scene())

    camera_ids = {task["camera_id"] for task in plan["render_tasks"]}

    assert {"camera_reveal", "camera_warm_lens_detail"}.issubset(camera_ids)
    assert "camera_topdown_debug" in camera_ids


def test_generate_scene_plan_without_scene_graph_emits_reduced_specificity_diagnostic() -> None:
    plan = generate_scene_plan(_example_brief())

    assert validate_scene_plan_payload(plan) == []
    diagnostic = plan["diagnostics"][-1]
    assert diagnostic["code"] == "SP4001"
    assert diagnostic["name"] == "brief_only_plan_reduced_specificity"
    assert diagnostic["severity"] == "warning"
    assert "--scene-graph" in diagnostic["repair_hint"]
