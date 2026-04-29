from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
from lathe.checker import check_program
from lathe.normalizer import normalize_program
from lathe.parser import parse_text
from lathe.parser.grammar import GRAMMAR_PATH, LatheParseError
from lathe.parser.transformer import _LatheTransformer
from lathe.planner import build_plan
from lathe.resolver import Resolver
from lathe.schema import get_schema


def _normalized(source: str) -> dict:
    return normalize_program(parse_text(source))


def _diagnostic_codes(source: str) -> list[str]:
    return [item["code"] for item in check_program(_normalized(source))]


MINIMAL_SCENE = """
scene alchemist_observatory {
  region region_central_chamber: interior {}
}
"""


ALCHEMIST_SCENE = """
style_pack dead_god_observatory {
  display_name = "Dead God Observatory"
  source.kind = curated
  palette.primary = bone_ivory
  palette.secondary = oxidized_copper
}

scene alchemist_observatory {
  version = 1
  brief = "A forgotten alchemist observatory inside the ribcage of a dead god."
  prompt = "A forgotten alchemist observatory inside the ribcage of a dead god."

  style style_dead_god_observatory {
    style_pack = dead_god_observatory
    mood = "sacred, eerie, antique"
    palette = [bone_ivory, oxidized_copper, black_glass, candle_gold]
  }

  region region_central_chamber: interior {
    purpose = "main reveal space"
    scale = "medium_room"
  }

  object obj_astrolabe_table: hero_prop from ornate_table {
    region = region_central_chamber
    material = oxidized_brass
  }

  object obj_rib_arches: environment_structure from bone_architecture {
    region = region_central_chamber
  }

  relationship rel_astrolabe_under_arches: frames {
    from = obj_rib_arches
    to = obj_astrolabe_table
  }

  camera camera_reveal: cinematic_wide {
    target = obj_astrolabe_table
  }

  light light_moonbeam: moonbeam {
    target = obj_astrolabe_table
  }

  export glb {
    path = "exports/alchemist_observatory.glb"
  }
}
"""


def test_parse_minimal_scene_declaration() -> None:
    scene = parse_text(MINIMAL_SCENE)["scenes"][0]

    assert scene["node_type"] == "scene"
    assert scene["name"] == "alchemist_observatory"
    assert scene["regions"] == [
        {
            "node_type": "scene_region",
            "name": "region_central_chamber",
            "type": "interior",
            "values": {},
        }
    ]


def test_parse_full_alchemist_observatory_scene_declaration() -> None:
    program = parse_text(ALCHEMIST_SCENE)
    style_pack = program["style_packs"][0]
    scene = program["scenes"][0]

    assert style_pack["node_type"] == "style_pack"
    assert style_pack["name"] == "dead_god_observatory"
    assert style_pack["values"]["source"]["kind"] == "curated"
    assert scene["values"]["version"] == 1
    assert scene["styles"][0]["name"] == "style_dead_god_observatory"
    assert scene["styles"][0]["values"]["style_pack"] == "dead_god_observatory"
    assert scene["objects"][0]["from"] == "ornate_table"
    assert scene["objects"][0]["values"]["region"] == "region_central_chamber"
    assert scene["relationships"][0]["type"] == "frames"
    assert scene["cameras"][0]["framing"] == "cinematic_wide"
    assert scene["lights"][0]["type"] == "moonbeam"
    assert scene["exports"][0]["values"]["path"] == "exports/alchemist_observatory.glb"


def test_parse_camera_intent_and_lighting_plan_aliases() -> None:
    source = """
scene alias_scene {
  region region_central_chamber: interior {}
  object obj_table: hero_prop from ornate_table {
    region = region_central_chamber
  }
  camera_intent camera_reveal: cinematic_wide {
    target = obj_table
  }
  lighting_plan light_moonbeam: moonbeam {
    target = obj_table
  }

  curiosity_anchor curiosity_warm_lens {
    attached_to = obj_table
    visible_clue = "The lens glows faintly."
    hidden_fact = "The lens still tracks a living star."
    suggested_user_actions = [inspect_lens, align_astrolabe]
    expansion_options.hidden_star_map.label = "Hidden Star Map"
    expansion_options.hidden_star_map.target_scope = obj_table
    expansion_options.hidden_star_map.required_assets = [star_map]
  }

  hidden_state hidden_warm_lens_truth {
    attached_to = obj_table
    fact = "The lens is warm because it tracks a living star."
    reveal_condition = "User inspects the lens."
    visible = false
  }
}
"""

    program = _normalized(source)
    scene = program["scenes"][0]

    assert scene["cameras"][0]["node_type"] == "scene_camera"
    assert scene["cameras"][0]["name"] == "camera_reveal"
    assert scene["cameras"][0]["framing"] == "cinematic_wide"
    assert scene["cameras"][0]["values"] == {"target": "obj_table"}
    assert scene["lights"][0]["node_type"] == "scene_light"
    assert scene["lights"][0]["name"] == "light_moonbeam"
    assert scene["lights"][0]["type"] == "moonbeam"
    assert scene["lights"][0]["values"] == {"target": "obj_table"}
    assert scene["curiosity_anchors"][0]["node_type"] == "scene_curiosity_anchor"
    assert scene["curiosity_anchors"][0]["name"] == "curiosity_warm_lens"
    assert scene["curiosity_anchors"][0]["values"]["attached_to"] == "obj_table"
    assert scene["curiosity_anchors"][0]["values"]["expansion_options"]["hidden_star_map"] == {
        "label": "Hidden Star Map",
        "target_scope": "obj_table",
        "required_assets": ["star_map"],
    }
    assert scene["hidden_state"][0]["node_type"] == "scene_hidden_state"
    assert scene["hidden_state"][0]["name"] == "hidden_warm_lens_truth"
    assert scene["hidden_state"][0]["values"]["attached_to"] == "obj_table"
    assert scene["hidden_state"][0]["values"]["visible"] is False

    validator = jsonschema.Draft202012Validator(get_schema())
    assert list(validator.iter_errors(program)) == []
    assert check_program(program) == []


def test_parse_object_gameplay_metadata_block() -> None:
    source = """
scene game_room {
  region region_central_chamber: interior {}
  object obj_archive_door: interactive from mechanical_door {
    region = region_central_chamber
    gameplay {
      interactable = true
      locked = true
      key_item = star_lens
      collision = box
      pivot = base_center
      tags = [door, quest]
      affordances.open_door.action = open
      affordances.open_door.requires = star_lens
    }
  }
}
"""

    program = _normalized(source)
    obj = program["scenes"][0]["objects"][0]

    assert obj["values"]["gameplay"] == {
        "interactable": True,
        "locked": True,
        "key_item": "star_lens",
        "collision": "box",
        "pivot": "base_center",
        "tags": ["door", "quest"],
        "affordances": {
            "open_door": {
                "action": "open",
                "requires": "star_lens",
            }
        },
    }

    validator = jsonschema.Draft202012Validator(get_schema())
    assert list(validator.iter_errors(program)) == []
    assert check_program(program) == []


def test_style_pack_decl_rejects_inert_uses_clause() -> None:
    source = """
style_pack derived_style uses base_style {
  display_name = "Derived"
}
"""

    with pytest.raises(LatheParseError):
        parse_text(source)


def test_grammar_and_transformer_scene_optional_qualifiers_are_separated() -> None:
    grammar = GRAMMAR_PATH.read_text(encoding="utf-8")
    transformer = _LatheTransformer()

    assert 'scene_type_clause: ":" IDENT' in grammar
    assert 'scene_from_clause: "from" qident' in grammar
    assert 'style_pack_decl: "style_pack" IDENT "{" assign_stmt* "}"' in grammar
    assert '"camera_intent" IDENT scene_type_clause?' in grammar
    assert '"lighting_plan" IDENT scene_type_clause?' in grammar
    assert '"curiosity_anchor" IDENT "{" assign_stmt* "}"' in grammar
    assert '"hidden_state" IDENT "{" assign_stmt* "}"' in grammar
    assert 'gameplay_scene_block: "gameplay" "{" assign_stmt* "}"' in grammar

    style_pack = transformer.style_pack_decl("dead_god_observatory", ("display_name", "Dead God Observatory"))
    region = transformer.region_scene_block("region_central_chamber", ("purpose", "main reveal"))
    gameplay = transformer.gameplay_scene_block(
        ("interactable", True),
        ("affordances.open_door.action", "open"),
    )
    obj = transformer.object_scene_block(
        "obj_astrolabe_table",
        transformer.scene_from_clause("ornate_table"),
        gameplay,
        ("region", "region_central_chamber"),
    )
    camera = transformer.camera_scene_block("camera_reveal", ("target", "obj_astrolabe_table"))
    camera_intent = transformer.camera_intent_scene_block(
        "camera_detail",
        transformer.scene_type_clause("inspection"),
        ("target", "obj_astrolabe_table"),
    )
    lighting_plan = transformer.lighting_plan_scene_block(
        "light_moonbeam",
        transformer.scene_type_clause("moonbeam"),
        ("target", "obj_astrolabe_table"),
    )
    curiosity_anchor = transformer.curiosity_anchor_scene_block(
        "curiosity_warm_lens",
        ("attached_to", "obj_astrolabe_table"),
    )
    hidden_state = transformer.hidden_state_scene_block(
        "hidden_warm_lens_truth",
        ("attached_to", "obj_astrolabe_table"),
    )

    assert style_pack["node_type"] == "style_pack"
    assert style_pack["values"]["display_name"] == "Dead God Observatory"
    assert region["type"] == ""
    assert region["values"]["purpose"] == "main reveal"
    assert obj["role"] == ""
    assert obj["from"] == "ornate_table"
    assert obj["values"]["region"] == "region_central_chamber"
    assert obj["values"]["gameplay"] == {"interactable": True, "affordances": {"open_door": {"action": "open"}}}
    assert camera["framing"] == ""
    assert camera["values"]["target"] == "obj_astrolabe_table"
    assert camera_intent["node_type"] == "scene_camera"
    assert camera_intent["framing"] == "inspection"
    assert camera_intent["values"]["target"] == "obj_astrolabe_table"
    assert lighting_plan["node_type"] == "scene_light"
    assert lighting_plan["type"] == "moonbeam"
    assert lighting_plan["values"]["target"] == "obj_astrolabe_table"
    assert curiosity_anchor["node_type"] == "scene_curiosity_anchor"
    assert curiosity_anchor["values"]["attached_to"] == "obj_astrolabe_table"
    assert hidden_state["node_type"] == "scene_hidden_state"
    assert hidden_state["values"]["attached_to"] == "obj_astrolabe_table"


def test_normalize_scene_defaults_and_schema_shape() -> None:
    program = _normalized(MINIMAL_SCENE)
    scene = program["scenes"][0]

    assert program["style_packs"] == []
    assert scene["version"] == 1
    assert scene["brief"] == ""
    assert scene["prompt"] == ""
    assert scene["objects"] == []
    assert scene["curiosity_anchors"] == []
    assert scene["hidden_state"] == []
    assert scene["regions"][0]["role"] == ""
    assert scene["regions"][0]["values"] == {}

    validator = jsonschema.Draft202012Validator(get_schema())
    assert list(validator.iter_errors(program)) == []


def test_scene_schema_rejects_child_in_wrong_collection() -> None:
    program = _normalized(ALCHEMIST_SCENE)
    bad_child = deepcopy(program["scenes"][0]["cameras"][0])
    program["scenes"][0]["objects"].append(bad_child)

    validator = jsonschema.Draft202012Validator(get_schema())
    errors = list(validator.iter_errors(program))

    assert errors
    assert any("scene_object" in error.message for error in errors)


def test_resolver_indexes_scene_declarations() -> None:
    program = _normalized(ALCHEMIST_SCENE)

    resolver = Resolver(program)

    assert "alchemist_observatory" in resolver.scene_map
    assert resolver.scene_map["alchemist_observatory"]["objects"][0]["name"] == "obj_astrolabe_table"


def test_checker_rejects_unknown_scene_references() -> None:
    source = """
scene bad_refs {
  region region_central_chamber: interior {}
  object obj_table: hero_prop from ornate_table {
    region = region_missing
  }
  relationship rel_bad: points_toward {
    from = obj_table
    to = obj_missing
  }
  camera camera_bad: cinematic_wide {
    target = obj_missing
  }
  light light_bad: moonbeam {
    target = obj_missing
  }
  curiosity_anchor curiosity_bad {
    attached_to = obj_missing
  }
  hidden_state hidden_bad {
    attached_to = obj_missing
  }
}
"""

    codes = _diagnostic_codes(source)

    assert "L5405" in codes
    assert "L5407" in codes
    assert "L5409" in codes
    assert "L5411" in codes
    assert "L5416" in codes
    assert "L5418" in codes


def test_checker_rejects_non_identifier_scene_reference_values() -> None:
    source = """
scene bad_reference_type {
  region region_central_chamber: interior {}
  object obj_table: hero_prop from ornate_table {
    region = [region_central_chamber]
  }
  camera camera_reveal: cinematic_wide {
    target = false
  }
  curiosity_anchor curiosity_bad {
    attached_to = false
  }
  hidden_state hidden_bad {
    attached_to = false
  }
}
"""

    codes = _diagnostic_codes(source)

    assert codes.count("L5412") == 4


def test_checker_validates_scene_style_pack_references() -> None:
    source = """
scene bad_style_pack {
  style style_scene {
    style_pack = missing_style_pack
  }
  region region_central_chamber: interior {}
}
"""

    assert "L5413" in _diagnostic_codes(source)


def test_checker_rejects_non_identifier_scene_style_pack_reference() -> None:
    source = """
scene bad_style_pack_reference_type {
  style style_scene {
    style_pack = [dead_god_observatory]
  }
  region region_central_chamber: interior {}
}
"""

    assert "L5414" in _diagnostic_codes(source)


def test_checker_rejects_empty_scene_style_pack_reference() -> None:
    source = """
scene bad_style_pack_reference_empty {
  style style_scene {
    style_pack = ""
  }
  region region_central_chamber: interior {}
}
"""

    assert "L5414" in _diagnostic_codes(source)


def test_checker_accepts_builtin_scene_style_pack_reference() -> None:
    source = """
scene builtin_style_pack {
  style style_scene {
    style_pack = dead_god_observatory
  }
  region region_central_chamber: interior {}
}
"""

    assert "L5413" not in _diagnostic_codes(source)


def test_checker_rejects_duplicate_scene_style_names() -> None:
    source = """
scene duplicate_styles {
  style style_scene {
    style_pack = dead_god_observatory
  }
  style style_scene {
    style_pack = dead_god_observatory
  }
  region region_central_chamber: interior {}
}
"""

    assert "L5401" in _diagnostic_codes(source)


def test_checker_rejects_object_region_that_points_to_non_region_scene_id() -> None:
    source = """
scene bad_region_namespace {
  region region_central_chamber: interior {}
  object obj_table: hero_prop from ornate_table {
    region = camera_reveal
  }
  camera camera_reveal: cinematic_wide {
    target = obj_table
  }
}
"""

    codes = _diagnostic_codes(source)

    assert "L5405" in codes


def test_checker_rejects_scene_local_id_contract_errors() -> None:
    source = """
scene bad_ids {
  region central_chamber: interior {}
  object table: hero_prop from ornate_table {
    region = central_chamber
  }
  relationship points: points_toward {
    from = table
    to = central_chamber
  }
  camera reveal: cinematic_wide {
    target = table
  }
  light moonbeam: moonbeam {
    target = table
  }
  curiosity_anchor warm_lens {
    attached_to = table
  }
  hidden_state warm_lens_truth {
    attached_to = table
  }
}
"""

    codes = _diagnostic_codes(source)

    assert "L5403" in codes
    assert "L5404" in codes
    assert "L5406" in codes
    assert "L5408" in codes
    assert "L5410" in codes
    assert "L5415" in codes
    assert "L5417" in codes


def test_planner_ignores_scene_declarations_until_scene_planning_is_invoked() -> None:
    source = (
        MINIMAL_SCENE
        + """
asset prop: hard_surface_prop {
  intent {
    role = "simple prop"
  }
}
"""
    )
    program = _normalized(source)

    plan = build_plan(program, "prop")

    assert plan["asset"] == "prop"
    assert plan["effective_asset"]["name"] == "prop"
    assert program["scenes"][0]["name"] == "alchemist_observatory"


def test_scene_source_contract_is_documented_in_spec() -> None:
    spec = (Path(__file__).resolve().parents[2] / "spec" / "lathe-v0.1.md").read_text(
        encoding="utf-8"
    )

    assert "Experimental v0.3 Scene Source Syntax" in spec
