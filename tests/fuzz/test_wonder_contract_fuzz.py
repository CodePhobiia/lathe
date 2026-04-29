"""Small Wonder contract fuzz tests for the Wave 6 CI lane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

hypothesis = pytest.importorskip("hypothesis", reason="Hypothesis is required for Wonder fuzz tests")
from hypothesis import HealthCheck, given, settings  # type: ignore[import-not-found]
from hypothesis import strategies as st  # type: ignore[import-not-found]
from lathe.paths import PathGuardError, safe_resolve
from lathe.scene.compare import compare_renders
from lathe.scene.ids import is_scene_entity_id, is_snake_id, scene_entity_id, snake_id
from lathe.scene.memory import append_memory_event_idempotent, create_world_memory, validate_world_memory
from lathe.scene.patch import apply_scene_patch
from lathe.wonder import load_and_validate_contract
from PIL import Image

pytestmark = pytest.mark.fuzz

MAX_EXAMPLES = 40
REPO_ROOT = Path(__file__).resolve().parents[2]
SCENE = json.loads((REPO_ROOT / "examples/wonder/alchemist_observatory/scene_graph.json").read_text(encoding="utf-8"))
BRIEF = json.loads((REPO_ROOT / "examples/wonder/alchemist_observatory/dream_brief.json").read_text(encoding="utf-8"))

_TEXT = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), max_codepoint=0x7F),
    max_size=80,
)
_JSON_POINTER = st.one_of(
    _TEXT,
    st.lists(_TEXT, min_size=0, max_size=4).map(
        lambda parts: "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)
    ),
)
_RGBA = st.tuples(
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
)


@given(pointer=_JSON_POINTER, value=_TEXT)
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_scene_patch_pointer_fuzz_rejects_or_applies_cleanly(pointer: str, value: str) -> None:
    patch: dict[str, Any] = {
        "schema_version": "lathe.scene_patch.v1",
        "patch_id": "patch_fuzz_pointer",
        "scope": "scene",
        "target_id": SCENE["scene_id"],
        "instruction": "Fuzz JSON pointer handling.",
        "allowed_changes": ["metadata"],
        "operations": [{"op": "replace", "path": pointer, "value": value}],
    }

    result = apply_scene_patch(SCENE, patch)

    assert isinstance(result.scene_graph, dict)
    assert isinstance(result.diagnostics, list)
    assert isinstance(result.rejected_operations, list)


@given(idempotency_suffix=_TEXT, secret_text=_TEXT)
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_world_memory_append_redaction_fuzz_is_idempotent(idempotency_suffix: str, secret_text: str) -> None:
    memory = create_world_memory(SCENE)
    event = {
        "event_id": "mem_fuzz_append",
        "type": "decision",
        "scope": "scene",
        "text": f"Contact user@example.com with Bearer abcdefghijklmnop token={secret_text}",
        "visibility": "private",
        "source": "fuzz",
        "metadata": {"api_key": "sk-proj-abcdefghijklmnopqrstuvwxyz123456"},
    }
    key = f"fuzz:{snake_id(idempotency_suffix, fallback='case')}"

    once = append_memory_event_idempotent(memory, event, key)
    twice = append_memory_event_idempotent(once, event, key)
    rendered = json.dumps(twice, sort_keys=True)

    assert once == twice
    assert "user@example.com" not in rendered
    assert "Bearer abcdefghijklmnop" not in rendered
    assert "sk-proj-abcdefghijklmnopqrstuvwxyz123456" not in rendered
    assert validate_world_memory(twice, scene_graph=SCENE) == []


@given(raw_path=_TEXT)
@settings(
    max_examples=MAX_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_path_safety_fuzz_resolves_under_root_or_rejects(tmp_path: Path, raw_path: str) -> None:
    try:
        resolved = safe_resolve(tmp_path, raw_path)
    except PathGuardError:
        return

    assert resolved.resolve(strict=False) == tmp_path.resolve(strict=False) or resolved.resolve(
        strict=False
    ).is_relative_to(tmp_path.resolve(strict=False))


@given(raw_id=_TEXT)
@settings(max_examples=MAX_EXAMPLES, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_id_normalization_fuzz_produces_valid_ids(raw_id: str) -> None:
    generic_id = snake_id(raw_id, fallback="fuzz")
    object_id = scene_entity_id("object", raw_id, suffix=1)

    assert is_snake_id(generic_id)
    assert is_scene_entity_id("object", object_id)
    assert len(generic_id) <= 80
    assert len(object_id) <= len("obj_") + 80


@given(before_color=_RGBA, after_color=_RGBA)
@settings(
    max_examples=MAX_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_render_comparison_metadata_fuzz_counts_single_pixel(
    tmp_path: Path,
    before_color: tuple[int, int, int, int],
    after_color: tuple[int, int, int, int],
) -> None:
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    Image.new("RGBA", (1, 1), before_color).save(before)
    Image.new("RGBA", (1, 1), after_color).save(after)

    comparison, diagnostics = compare_renders(before, after)

    assert diagnostics == []
    assert comparison is not None
    assert comparison["dimensions"] == {"width": 1, "height": 1}
    expected_changed = 0 if before_color == after_color else 1
    assert comparison["pixel_delta"]["changed_pixels"] == expected_changed


@given(title=_TEXT, sentence=_TEXT, scale=_TEXT)
@settings(
    max_examples=MAX_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_dream_brief_json_ingress_fuzz_returns_payload_and_diagnostics(
    tmp_path: Path,
    title: str,
    sentence: str,
    scale: str,
) -> None:
    payload = dict(BRIEF)
    payload.update({"title": title, "one_sentence": sentence, "scale": scale})
    path = tmp_path / "dream_brief.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded, diagnostics = load_and_validate_contract("dream_brief", path)

    assert loaded == payload
    assert isinstance(diagnostics, list)
    assert all(isinstance(diagnostic, dict) for diagnostic in diagnostics)


@given(scene_id=_TEXT, object_id=_TEXT, region_id=_TEXT)
@settings(
    max_examples=MAX_EXAMPLES,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_scene_graph_json_ingress_fuzz_returns_payload_and_diagnostics(
    tmp_path: Path,
    scene_id: str,
    object_id: str,
    region_id: str,
) -> None:
    payload = dict(SCENE)
    payload["scene_id"] = scene_id
    payload["regions"] = [dict(SCENE["regions"][0], region_id=region_id)]
    payload["objects"] = [dict(SCENE["objects"][0], object_id=object_id, region=region_id)]
    path = tmp_path / "scene_graph.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded, diagnostics = load_and_validate_contract("scene_graph", path)

    assert loaded == payload
    assert isinstance(diagnostics, list)
    assert all(isinstance(diagnostic, dict) for diagnostic in diagnostics)
