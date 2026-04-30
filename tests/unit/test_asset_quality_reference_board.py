"""Phase 11 tests for ``lathe.asset_quality.reference_board``.

Covers per task #11.1-#11.5 of
``docs/asset-quality/improvement-tasklist.md``:

- frozenness contract for every reference dataclass;
- v1 payload shape (version + required keys);
- skipped-evidence contract (``reference_board_not_loaded``,
  ``reference_missing``, ``reference_malformed``);
- disk loader behaviour (missing directory, missing sub-file,
  malformed JSON, extra fields, list/object form tolerance);
- summary counts and the ``all_required_present`` flag;
- design-brief negative-constraint merge (with dedupe and
  preservation of existing-first ordering);
- pipeline-level publication of ``runtime["reference_board"]``.

All tests run deterministically with no real network or external
service.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from lathe.asset_quality.design_brief import evaluate_design_brief
from lathe.asset_quality.reference_board import (
    REFERENCE_BOARD_VERSION,
    MaterialReference,
    MoodReference,
    NegativeReference,
    ReferenceBoard,
    SilhouetteReference,
    SkippedReason,
    evaluate_reference_board,
    load_reference_board,
)
from lathe.core.stages.validate import _PIPELINE


_REPO_ROOT = Path(__file__).resolve().parents[2]
_INDUSTRIAL_FIXTURES = (
    _REPO_ROOT / "examples" / "refs" / "asset_quality" / "industrial_crate"
)


def _industrial_runtime() -> dict[str, Any]:
    raw = load_reference_board("industrial_crate", _REPO_ROOT / "examples" / "refs" / "asset_quality")
    assert raw is not None
    return {"_reference_board": raw}


# ---------------------------------------------------------------------------
# Frozenness contracts
# ---------------------------------------------------------------------------


def test_mood_reference_is_frozen() -> None:
    mood = MoodReference(
        palette=("rusted_iron",),
        lighting="warm",
        era="industrial",
        descriptors=("aged",),
    )

    assert dataclasses.is_dataclass(MoodReference)
    with pytest.raises(dataclasses.FrozenInstanceError):
        mood.lighting = "cold"  # type: ignore[misc]


def test_silhouette_reference_is_frozen() -> None:
    silhouette = SilhouetteReference(
        intent="cube",
        proportions={"width_to_height": 1.0},
        descriptors=("blocky",),
        image_uri=None,
    )

    assert dataclasses.is_dataclass(SilhouetteReference)
    with pytest.raises(dataclasses.FrozenInstanceError):
        silhouette.intent = "sphere"  # type: ignore[misc]


def test_material_reference_is_frozen() -> None:
    material = MaterialReference(
        target="painted_steel",
        pbr_hints={"roughness": 0.5},
        descriptors=("matte",),
    )

    assert dataclasses.is_dataclass(MaterialReference)
    with pytest.raises(dataclasses.FrozenInstanceError):
        material.target = "chrome"  # type: ignore[misc]


def test_negative_reference_is_frozen() -> None:
    negative = NegativeReference(constraint="no_chrome", rationale="matte_only")

    assert dataclasses.is_dataclass(NegativeReference)
    with pytest.raises(dataclasses.FrozenInstanceError):
        negative.constraint = "no_brass"  # type: ignore[misc]


def test_reference_board_is_frozen() -> None:
    board = ReferenceBoard(
        asset_name="industrial_crate",
        family="industrial_crate",
        mood=None,
        silhouettes=(),
        materials=(),
        negatives=(),
    )

    assert dataclasses.is_dataclass(ReferenceBoard)
    with pytest.raises(dataclasses.FrozenInstanceError):
        board.asset_name = "another"  # type: ignore[misc]


def test_skipped_reason_is_frozen() -> None:
    skipped = SkippedReason(category="mood", reason="reference_missing")

    assert dataclasses.is_dataclass(SkippedReason)
    with pytest.raises(dataclasses.FrozenInstanceError):
        skipped.category = "silhouette"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Validator payload shape
# ---------------------------------------------------------------------------


def test_evaluate_reference_board_returns_v1_payload() -> None:
    runtime = _industrial_runtime()
    payload = evaluate_reference_board({"name": "industrial_crate"}, runtime)

    assert payload["version"] == REFERENCE_BOARD_VERSION
    assert payload["version"] == "reference_board_v1"
    # Phase 13 added an additive ``user_provided_via_experimental`` key.
    # The Phase 11 baseline keys must remain a subset of the payload.
    assert {
        "version",
        "asset_name",
        "family",
        "board",
        "summary",
        "skipped_reasons",
        "warnings",
        "diagnostics",
    }.issubset(payload.keys())
    assert set(payload["board"].keys()) == {
        "mood",
        "silhouettes",
        "materials",
        "negatives",
    }
    assert set(payload["summary"].keys()) == {
        "has_mood",
        "silhouette_count",
        "material_count",
        "negative_count",
        "all_required_present",
    }
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["diagnostics"], list)


def test_no_reference_board_in_runtime_emits_not_loaded() -> None:
    payload = evaluate_reference_board({"name": "industrial_crate"}, {})

    assert payload["board"]["mood"] is None
    assert payload["board"]["silhouettes"] == []
    assert payload["board"]["materials"] == []
    assert payload["board"]["negatives"] == []
    assert payload["summary"]["all_required_present"] is False
    assert payload["skipped_reasons"] == [
        {"category": "reference_board", "reason": "reference_board_not_loaded"}
    ]


def test_explicit_none_reference_board_in_runtime_emits_not_loaded() -> None:
    payload = evaluate_reference_board(
        {"name": "industrial_crate"},
        {"_reference_board": None},
    )

    assert payload["board"]["mood"] is None
    assert payload["board"]["silhouettes"] == []
    assert payload["skipped_reasons"] == [
        {"category": "reference_board", "reason": "reference_board_not_loaded"}
    ]


def test_family_resolved_from_design_brief_inference_when_raw_family_absent() -> None:
    payload = evaluate_reference_board(
        {"name": "industrial_crate"},
        {
            "design_brief": {
                "family_inference": {"matched_family": "industrial_crate"}
            },
            "_reference_board": {
                "asset_name": "industrial_crate",
                "family": None,
                "mood": None,
                "silhouettes": [],
                "materials": [],
                "negatives": [],
                "skipped": [],
            },
        },
    )

    assert payload["family"] == "industrial_crate"


# ---------------------------------------------------------------------------
# Loader behaviour
# ---------------------------------------------------------------------------


def test_load_reference_board_returns_none_for_missing_directory(tmp_path: Path) -> None:
    raw = load_reference_board("industrial_crate", tmp_path)

    assert raw is None


def test_load_reference_board_loads_industrial_crate_fixtures() -> None:
    raw = load_reference_board(
        "industrial_crate", _REPO_ROOT / "examples" / "refs" / "asset_quality"
    )

    assert raw is not None
    assert raw["asset_name"] == "industrial_crate"
    assert isinstance(raw["mood"], dict)
    assert raw["mood"]["palette"] == [
        "weathered_steel",
        "oxidized_brass",
        "soot_smudge",
    ]
    assert isinstance(raw["silhouettes"], list)
    assert len(raw["silhouettes"]) == 1
    assert isinstance(raw["materials"], list)
    assert len(raw["materials"]) == 2
    assert isinstance(raw["negatives"], list)
    assert len(raw["negatives"]) == 3
    assert raw["skipped"] == []


def test_load_reference_board_skips_missing_subfile(tmp_path: Path) -> None:
    asset_dir = tmp_path / "demo_asset"
    asset_dir.mkdir()
    (asset_dir / "mood.json").write_text(
        json.dumps({"palette": ["a"], "lighting": "x", "era": "y", "descriptors": []}),
        encoding="utf-8",
    )

    raw = load_reference_board("demo_asset", tmp_path)

    assert raw is not None
    assert raw["mood"] is not None
    skipped_categories = {entry["category"] for entry in raw["skipped"]}
    assert skipped_categories == {"silhouette", "materials", "negative"}
    for entry in raw["skipped"]:
        assert entry["reason"] == "reference_missing"


def test_load_reference_board_skips_malformed_json(tmp_path: Path) -> None:
    asset_dir = tmp_path / "demo_asset"
    asset_dir.mkdir()
    (asset_dir / "mood.json").write_text("{ not valid json", encoding="utf-8")

    raw = load_reference_board("demo_asset", tmp_path)

    assert raw is not None
    assert raw["mood"] is None
    malformed = [
        entry for entry in raw["skipped"] if entry["reason"] == "reference_malformed"
    ]
    assert any(entry["category"] == "mood" for entry in malformed)


def test_loader_tolerates_extra_fields(tmp_path: Path) -> None:
    asset_dir = tmp_path / "demo_asset"
    asset_dir.mkdir()
    (asset_dir / "mood.json").write_text(
        json.dumps(
            {
                "palette": ["a"],
                "lighting": "warm",
                "era": "industrial",
                "descriptors": ["aged"],
                "future_field": "ignored",
                "experimental": {"nested": True},
            }
        ),
        encoding="utf-8",
    )
    (asset_dir / "silhouette.json").write_text(
        json.dumps(
            {
                "silhouettes": [
                    {
                        "intent": "cube",
                        "proportions": {"width_to_height": 1.0},
                        "descriptors": [],
                        "image_uri": None,
                        "extra": "ignored",
                    }
                ],
                "trailing_metadata": {"version": "v0.99"},
            }
        ),
        encoding="utf-8",
    )

    raw = load_reference_board("demo_asset", tmp_path)
    payload = evaluate_reference_board(
        {"name": "demo_asset"}, {"_reference_board": raw}
    )

    assert payload["version"] == REFERENCE_BOARD_VERSION
    assert payload["board"]["mood"]["palette"] == ["a"]
    assert payload["board"]["silhouettes"][0]["intent"] == "cube"


def test_loader_tolerates_top_level_arrays_or_objects(tmp_path: Path) -> None:
    asset_dir = tmp_path / "demo_asset"
    asset_dir.mkdir()
    # Object form (canonical) for silhouette.
    (asset_dir / "silhouette.json").write_text(
        json.dumps(
            {
                "silhouettes": [
                    {
                        "intent": "cube",
                        "proportions": {"width_to_height": 1.0},
                        "descriptors": [],
                        "image_uri": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    # Direct list form for materials.
    (asset_dir / "materials.json").write_text(
        json.dumps(
            [
                {
                    "target": "steel",
                    "pbr_hints": {"roughness": 0.5},
                    "descriptors": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    # Direct list form for negatives.
    (asset_dir / "negative.json").write_text(
        json.dumps(
            [{"constraint": "no_chrome", "rationale": "matte_only"}],
        ),
        encoding="utf-8",
    )

    raw = load_reference_board("demo_asset", tmp_path)

    assert raw is not None
    assert len(raw["silhouettes"]) == 1
    assert len(raw["materials"]) == 1
    assert len(raw["negatives"]) == 1


# ---------------------------------------------------------------------------
# Summary semantics
# ---------------------------------------------------------------------------


def test_evaluate_reference_board_summary_counts_match_board() -> None:
    runtime = _industrial_runtime()
    payload = evaluate_reference_board({"name": "industrial_crate"}, runtime)
    summary = payload["summary"]

    assert summary["has_mood"] is True
    assert summary["silhouette_count"] == len(payload["board"]["silhouettes"])
    assert summary["material_count"] == len(payload["board"]["materials"])
    assert summary["negative_count"] == len(payload["board"]["negatives"])
    assert summary["silhouette_count"] == 1
    assert summary["material_count"] == 2
    assert summary["negative_count"] == 3


def test_evaluate_reference_board_all_required_present_when_mood_silhouette_material_present() -> None:
    runtime = _industrial_runtime()
    payload = evaluate_reference_board({"name": "industrial_crate"}, runtime)

    assert payload["summary"]["all_required_present"] is True


def test_evaluate_reference_board_all_required_absent_emits_summary_false() -> None:
    raw = {
        "asset_name": "demo_asset",
        "family": None,
        "mood": None,
        "silhouettes": [],
        "materials": [],
        "negatives": [],
        "skipped": [
            {"category": "mood", "reason": "reference_missing"},
            {"category": "silhouette", "reason": "reference_missing"},
            {"category": "materials", "reason": "reference_missing"},
            {"category": "negative", "reason": "reference_missing"},
        ],
    }
    payload = evaluate_reference_board(
        {"name": "demo_asset"}, {"_reference_board": raw}
    )

    assert payload["summary"]["all_required_present"] is False
    assert payload["summary"]["has_mood"] is False
    assert payload["summary"]["silhouette_count"] == 0
    assert payload["summary"]["material_count"] == 0


# ---------------------------------------------------------------------------
# Design brief integration
# ---------------------------------------------------------------------------


def test_negative_constraints_merge_into_design_brief() -> None:
    raw = {
        "asset_name": "industrial_crate",
        "family": None,
        "mood": None,
        "silhouettes": [],
        "materials": [],
        "negatives": [
            {"constraint": "no_chrome_finishes", "rationale": "matte"},
            {"constraint": "no_clean_geometry", "rationale": "show_wear"},
        ],
        "skipped": [],
    }
    payload = evaluate_design_brief(
        {"name": "industrial_crate"}, {"_reference_board": raw}
    )
    constraints = payload["brief"]["negative_constraints"]

    assert "toy_like" in constraints
    assert "random_faceting" in constraints
    assert "ornate" in constraints
    assert "no_chrome_finishes" in constraints
    assert "no_clean_geometry" in constraints
    # Existing constraints come first, references after.
    assert constraints.index("toy_like") < constraints.index("no_chrome_finishes")


def test_negative_constraints_dedupe() -> None:
    raw = {
        "asset_name": "industrial_crate",
        "family": None,
        "mood": None,
        "silhouettes": [],
        "materials": [],
        "negatives": [
            {"constraint": "toy_like", "rationale": "not_toy_like"},
            {"constraint": "no_chrome_finishes", "rationale": "matte"},
            {"constraint": "no_chrome_finishes", "rationale": "matte_again"},
        ],
        "skipped": [],
    }
    payload = evaluate_design_brief(
        {"name": "industrial_crate"}, {"_reference_board": raw}
    )
    constraints = payload["brief"]["negative_constraints"]

    assert constraints.count("toy_like") == 1
    assert constraints.count("no_chrome_finishes") == 1


def test_design_brief_unchanged_when_no_reference_board() -> None:
    payload = evaluate_design_brief({"name": "industrial_crate"}, {})

    assert payload["brief"]["negative_constraints"] == [
        "toy_like",
        "random_faceting",
        "ornate",
    ]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_evidence_is_deterministic() -> None:
    runtime = _industrial_runtime()
    asset = {"name": "industrial_crate"}
    first = evaluate_reference_board(asset, runtime)
    second = evaluate_reference_board(asset, runtime)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_skipped_reasons_sorted_deterministically() -> None:
    raw = {
        "asset_name": "demo_asset",
        "family": None,
        "mood": None,
        "silhouettes": [],
        "materials": [],
        "negatives": [],
        "skipped": [
            {"category": "negative", "reason": "reference_missing"},
            {"category": "mood", "reason": "reference_missing"},
            {"category": "silhouette", "reason": "reference_missing"},
            {"category": "materials", "reason": "reference_missing"},
        ],
    }
    payload = evaluate_reference_board({"name": "demo_asset"}, {"_reference_board": raw})

    categories = [entry["category"] for entry in payload["skipped_reasons"]]
    assert categories == sorted(categories)


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


def test_validator_pipeline_publishes_reference_board_to_runtime() -> None:
    runtime: dict[str, Any] = _industrial_runtime()
    asset = {"name": "industrial_crate"}

    cert_bundle = _PIPELINE.run(runtime, asset, artifacts={})

    assert "reference_board" in cert_bundle["validators"]
    evidence = cert_bundle["validators"]["reference_board"]["evidence"]
    assert evidence["version"] == REFERENCE_BOARD_VERSION
    assert evidence["summary"]["all_required_present"] is True


def test_industrial_crate_fixtures_match_v1_schema() -> None:
    runtime = _industrial_runtime()
    payload = evaluate_reference_board({"name": "industrial_crate"}, runtime)

    assert payload["version"] == "reference_board_v1"
    assert payload["asset_name"] == "industrial_crate"
    assert payload["board"]["mood"] is not None
    assert payload["board"]["mood"]["palette"][0] == "weathered_steel"
    silhouette = payload["board"]["silhouettes"][0]
    assert silhouette["intent"] == "rectangular_chest_with_corner_guards"
    assert silhouette["image_uri"] is None
    materials = payload["board"]["materials"]
    assert {entry["target"] for entry in materials} == {
        "painted_steel_body",
        "dark_bare_metal_underlayer",
    }
    negatives = payload["board"]["negatives"]
    assert {entry["constraint"] for entry in negatives} == {
        "no_chrome_finishes",
        "no_clean_geometry",
        "no_consumer_aesthetics",
    }
