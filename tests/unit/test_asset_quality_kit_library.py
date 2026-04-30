"""Phase 12 tests for ``lathe.asset_quality.kit_library``.

Covers per the Phase 12 task in
``docs/asset-quality/improvement-tasklist.md``:

- frozenness contract for every kit-library dataclass;
- v1 payload shape (version + required keys);
- skipped-evidence contract (``kit_library_not_loaded``,
  ``kit_library_directory_missing``, ``category_directory_missing``,
  ``kit_part_unreadable``, ``kit_part_malformed``,
  ``kit_part_schema_violation:<detail>``);
- disk loader behaviour (missing directory, missing category,
  malformed JSON, schema violations);
- lookup helpers (``lookup_kit_part``, ``kit_parts_by_category``,
  ``kit_parts_for_family``) including wildcard family matching;
- summary counts and the ``all_required_categories_present`` flag;
- pipeline-level publication of the kit_library validator;
- real fixture conformance against the in-module schema.

All tests run deterministically with no real network or external
service.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from lathe.asset_quality.kit_library import (
    KIT_LIBRARY_VERSION,
    REQUIRED_CATEGORIES,
    KitLibrary,
    KitPart,
    KitSocket,
    LODBehavior,
    PlacementConstraint,
    Provenance,
    ScaleRange,
    SkippedReason,
    evaluate_kit_library,
    kit_parts_by_category,
    kit_parts_for_family,
    load_kit_library,
    lookup_kit_part,
)
from lathe.core.stages.validate import _PIPELINE


_REPO_ROOT = Path(__file__).resolve().parents[2]
_KIT_LIBRARY_BASE = _REPO_ROOT / "std" / "kits" / "hardsurface"


# ---------------------------------------------------------------------------
# Frozenness contracts
# ---------------------------------------------------------------------------


def test_kit_socket_is_frozen() -> None:
    socket = KitSocket(name="anchor", anchor_axis="+x", default_position=(0.0, 0.0, 0.0))

    assert dataclasses.is_dataclass(KitSocket)
    with pytest.raises(dataclasses.FrozenInstanceError):
        socket.name = "other"  # type: ignore[misc]


def test_placement_constraint_is_frozen() -> None:
    constraint = PlacementConstraint(face="any", normal_axis="any", requires_flat_surface=True)

    assert dataclasses.is_dataclass(PlacementConstraint)
    with pytest.raises(dataclasses.FrozenInstanceError):
        constraint.face = "top"  # type: ignore[misc]


def test_scale_range_is_frozen() -> None:
    scale = ScaleRange(min_scale=0.5, max_scale=1.5)

    assert dataclasses.is_dataclass(ScaleRange)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scale.min_scale = 0.9  # type: ignore[misc]


def test_lod_behavior_is_frozen() -> None:
    lod = LODBehavior(strategy="drop_at_lod1", retained_for_collision=False)

    assert dataclasses.is_dataclass(LODBehavior)
    with pytest.raises(dataclasses.FrozenInstanceError):
        lod.strategy = "drop_at_lod2"  # type: ignore[misc]


def test_provenance_is_frozen() -> None:
    provenance = Provenance(
        source="std/kits/hardsurface (Phase 12 internal)",
        version="v1",
        license="internal",
    )

    assert dataclasses.is_dataclass(Provenance)
    with pytest.raises(dataclasses.FrozenInstanceError):
        provenance.version = "v2"  # type: ignore[misc]


def _example_part() -> KitPart:
    return KitPart(
        name="example",
        category="fasteners",
        kind="procedural",
        procedural_recipe={"primitive": "stub"},
        mesh_stub_uri=None,
        material_zones=("bare_metal_fastener",),
        sockets=(KitSocket(name="anchor", anchor_axis="-z", default_position=(0.0, 0.0, 0.0)),),
        placement_constraints=PlacementConstraint(
            face="any", normal_axis="any", requires_flat_surface=True
        ),
        scale_range=ScaleRange(min_scale=0.8, max_scale=1.2),
        allowed_families=("industrial_crate",),
        lod_behavior=LODBehavior(strategy="drop_at_lod2", retained_for_collision=False),
        bake_group="trim_metal",
        provenance=Provenance(
            source="std/kits/hardsurface (Phase 12 internal)",
            version="v1",
            license="internal",
        ),
    )


def test_kit_part_is_frozen() -> None:
    part = _example_part()

    assert dataclasses.is_dataclass(KitPart)
    with pytest.raises(dataclasses.FrozenInstanceError):
        part.name = "other"  # type: ignore[misc]


def test_kit_library_is_frozen() -> None:
    library = KitLibrary(base_path="", parts=(), skipped=())

    assert dataclasses.is_dataclass(KitLibrary)
    with pytest.raises(dataclasses.FrozenInstanceError):
        library.base_path = "other"  # type: ignore[misc]


def test_skipped_reason_is_frozen() -> None:
    record = SkippedReason(category="kit_library", reason="kit_library_not_loaded")

    assert dataclasses.is_dataclass(SkippedReason)
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.category = "fasteners"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Validator payload shape
# ---------------------------------------------------------------------------


def test_evaluate_kit_library_returns_v1_payload() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime = {"_kit_library": library}
    payload = evaluate_kit_library({"name": "industrial_crate"}, runtime)

    assert payload["version"] == KIT_LIBRARY_VERSION
    assert payload["version"] == "kit_library_v1"
    assert set(payload.keys()) == {
        "version",
        "asset_name",
        "family",
        "library",
        "summary",
        "skipped_reasons",
        "warnings",
        "diagnostics",
    }
    assert set(payload["library"].keys()) == {"base_path", "parts", "skipped"}
    assert set(payload["summary"].keys()) == {
        "part_count",
        "parts_by_category",
        "categories_covered",
        "all_required_categories_present",
        "parts_for_family_count",
    }
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["diagnostics"], list)


def test_no_kit_library_in_runtime_emits_not_loaded() -> None:
    payload = evaluate_kit_library({"name": "industrial_crate"}, {})

    assert payload["library"]["parts"] == []
    assert payload["summary"]["part_count"] == 0
    assert payload["summary"]["categories_covered"] == 0
    assert payload["summary"]["all_required_categories_present"] is False
    assert payload["summary"]["parts_for_family_count"] == 0
    assert payload["skipped_reasons"] == [
        {"category": "kit_library", "reason": "kit_library_not_loaded"}
    ]


def test_explicit_none_kit_library_in_runtime_emits_not_loaded() -> None:
    payload = evaluate_kit_library(
        {"name": "industrial_crate"},
        {"_kit_library": None},
    )

    assert payload["library"]["parts"] == []
    assert payload["skipped_reasons"] == [
        {"category": "kit_library", "reason": "kit_library_not_loaded"}
    ]


# ---------------------------------------------------------------------------
# Loader behaviour
# ---------------------------------------------------------------------------


def test_load_kit_library_returns_empty_for_missing_directory(tmp_path: Path) -> None:
    library = load_kit_library(tmp_path / "nope")

    assert library.parts == ()
    assert len(library.skipped) == 1
    assert library.skipped[0].category == "kit_library"
    assert library.skipped[0].reason == "kit_library_directory_missing"


def test_load_kit_library_loads_real_fixtures() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)

    assert len(library.parts) >= 5
    categories_loaded = {part.category for part in library.parts}
    assert categories_loaded == set(REQUIRED_CATEGORIES)
    assert library.skipped == ()


def test_load_kit_library_skips_malformed_json(tmp_path: Path) -> None:
    fasteners = tmp_path / "fasteners"
    fasteners.mkdir()
    (fasteners / "broken.json").write_text("{ not valid json", encoding="utf-8")

    library = load_kit_library(tmp_path)

    malformed = [
        record
        for record in library.skipped
        if record.reason == "kit_part_malformed"
        and record.category == "kit_part_broken.json"
    ]
    assert len(malformed) == 1


def test_load_kit_library_skips_schema_violation(tmp_path: Path) -> None:
    fasteners = tmp_path / "fasteners"
    fasteners.mkdir()
    payload: dict[str, Any] = {
        # missing the required ``category`` field
        "name": "broken_bolt",
        "kind": "procedural",
        "procedural_recipe": {},
        "material_zones": ["bare_metal_fastener"],
        "sockets": [],
        "placement_constraints": {
            "face": "any",
            "normal_axis": "any",
            "requires_flat_surface": True,
        },
        "scale_range": {"min": 0.8, "max": 1.2},
        "allowed_families": ["*"],
        "lod_behavior": {"strategy": "drop_at_lod2", "retained_for_collision": False},
        "bake_group": "trim_metal",
        "provenance": {
            "source": "std/kits/hardsurface (Phase 12 internal)",
            "version": "v1",
            "license": "internal",
        },
    }
    (fasteners / "broken.json").write_text(json.dumps(payload), encoding="utf-8")

    library = load_kit_library(tmp_path)

    violations = [record for record in library.skipped if "schema_violation" in record.reason]
    assert len(violations) == 1
    assert violations[0].category == "kit_part_broken.json"
    assert violations[0].reason.startswith("kit_part_schema_violation:")
    assert "missing_field_category" in violations[0].reason


def test_load_kit_library_rejects_unexpected_top_level_field(tmp_path: Path) -> None:
    fasteners = tmp_path / "fasteners"
    fasteners.mkdir()
    payload: dict[str, Any] = {
        "name": "extra_field_bolt",
        "category": "fasteners",
        "kind": "procedural",
        "procedural_recipe": {},
        "material_zones": ["bare_metal_fastener"],
        "sockets": [],
        "placement_constraints": {
            "face": "any",
            "normal_axis": "any",
            "requires_flat_surface": True,
        },
        "scale_range": {"min": 0.8, "max": 1.2},
        "allowed_families": ["*"],
        "lod_behavior": {"strategy": "drop_at_lod2", "retained_for_collision": False},
        "bake_group": "trim_metal",
        "provenance": {
            "source": "std/kits/hardsurface (Phase 12 internal)",
            "version": "v1",
            "license": "internal",
        },
        "unexpected_extra": "this_field_is_not_in_the_schema",
    }
    (fasteners / "extra.json").write_text(json.dumps(payload), encoding="utf-8")

    library = load_kit_library(tmp_path)

    violations = [record for record in library.skipped if "schema_violation" in record.reason]
    assert len(violations) == 1
    assert "unexpected_field_unexpected_extra" in violations[0].reason


def test_load_kit_library_skips_when_category_missing(tmp_path: Path) -> None:
    # Empty base directory -> every category subdirectory is missing.
    tmp_path.mkdir(parents=True, exist_ok=True)

    library = load_kit_library(tmp_path)

    categories_skipped = {record.category for record in library.skipped}
    assert categories_skipped == {f"category_{name}" for name in REQUIRED_CATEGORIES}
    for record in library.skipped:
        assert record.reason == "category_directory_missing"


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def test_lookup_kit_part_returns_part_when_present() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)

    part = lookup_kit_part(library, "hex_bolt_m6")

    assert part is not None
    assert part.category == "fasteners"


def test_lookup_kit_part_returns_none_for_missing_name() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)

    assert lookup_kit_part(library, "does_not_exist") is None
    assert lookup_kit_part(library, "") is None


def test_kit_parts_by_category_filters_correctly() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)

    fasteners = kit_parts_by_category(library, "fasteners")

    assert len(fasteners) >= 1
    for part in fasteners:
        assert part.category == "fasteners"
    names = [part.name for part in fasteners]
    assert names == sorted(names)


def test_kit_parts_by_category_returns_empty_for_unknown_category() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)

    assert kit_parts_by_category(library, "hovercrafts") == ()


def test_kit_parts_for_family_filters_by_allowed_families() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)

    industrial = kit_parts_for_family(library, "industrial_crate")

    for part in industrial:
        assert "industrial_crate" in part.allowed_families or "*" in part.allowed_families


def test_kit_parts_for_family_includes_wildcard_parts() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)

    matched = kit_parts_for_family(library, "completely_new_family_42")

    assert all("*" in part.allowed_families for part in matched)
    # We have at least one wildcard fixture (flat_rivet_4mm).
    assert any(part.name == "flat_rivet_4mm" for part in matched)


def test_kit_parts_for_family_excludes_disallowed() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)

    matched = kit_parts_for_family(library, "completely_new_family_42")

    # No part with explicit families that don't include the test family
    # should be in the matched list — every match must have either ``*``
    # or the literal family name.
    for part in matched:
        assert "*" in part.allowed_families or "completely_new_family_42" in part.allowed_families


# ---------------------------------------------------------------------------
# Summary semantics
# ---------------------------------------------------------------------------


def test_evaluate_kit_library_summary_counts_match_loaded_parts() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime = {"_kit_library": library}

    payload = evaluate_kit_library({"name": "industrial_crate"}, runtime)

    summary = payload["summary"]
    assert summary["part_count"] == len(library.parts)
    total_by_category = sum(summary["parts_by_category"].values())
    assert total_by_category == summary["part_count"]
    assert summary["categories_covered"] == 5
    assert summary["all_required_categories_present"] is True


def test_all_required_categories_present_when_all_5_have_parts() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime = {"_kit_library": library}

    payload = evaluate_kit_library({"name": "industrial_crate"}, runtime)

    assert payload["summary"]["all_required_categories_present"] is True


def test_all_required_categories_absent_when_one_category_empty(tmp_path: Path) -> None:
    # Build a library with parts in only four of the five categories.
    for category in REQUIRED_CATEGORIES[:-1]:
        (tmp_path / category).mkdir()
        payload = {
            "name": f"sample_{category}",
            "category": category,
            "kind": "procedural",
            "procedural_recipe": {"primitive": "stub"},
            "material_zones": ["bare_metal_fastener"],
            "sockets": [],
            "placement_constraints": {
                "face": "any",
                "normal_axis": "any",
                "requires_flat_surface": True,
            },
            "scale_range": {"min": 0.8, "max": 1.2},
            "allowed_families": ["*"],
            "lod_behavior": {"strategy": "drop_at_lod2", "retained_for_collision": False},
            "bake_group": "trim_metal",
            "provenance": {
                "source": "std/kits/hardsurface (Phase 12 internal)",
                "version": "v1",
                "license": "internal",
            },
        }
        (tmp_path / category / f"sample_{category}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
    library = load_kit_library(tmp_path)
    runtime = {"_kit_library": library}

    payload = evaluate_kit_library({"name": "industrial_crate"}, runtime)

    assert payload["summary"]["categories_covered"] == 4
    assert payload["summary"]["all_required_categories_present"] is False


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_evidence_is_deterministic() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime = {"_kit_library": library}
    asset = {"name": "industrial_crate"}

    first = evaluate_kit_library(asset, runtime)
    second = evaluate_kit_library(asset, runtime)

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_skipped_reasons_sorted_deterministically(tmp_path: Path) -> None:
    library = load_kit_library(tmp_path)
    runtime = {"_kit_library": library}

    payload = evaluate_kit_library({"name": "industrial_crate"}, runtime)

    pairs = [(entry["category"], entry["reason"]) for entry in payload["skipped_reasons"]]
    assert pairs == sorted(pairs)


# ---------------------------------------------------------------------------
# Pipeline integration
# ---------------------------------------------------------------------------


def test_validator_pipeline_publishes_kit_library_to_runtime() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime: dict[str, Any] = {"_kit_library": library}
    asset = {"name": "industrial_crate"}

    cert_bundle = _PIPELINE.run(runtime, asset, artifacts={})

    assert "kit_library" in cert_bundle["validators"]
    evidence = cert_bundle["validators"]["kit_library"]["evidence"]
    assert evidence["version"] == KIT_LIBRARY_VERSION
    assert evidence["summary"]["all_required_categories_present"] is True


def test_family_resolved_from_design_brief_inference() -> None:
    library = load_kit_library(_KIT_LIBRARY_BASE)
    runtime = {
        "_kit_library": library,
        "design_brief": {"family_inference": {"matched_family": "industrial_crate"}},
    }

    payload = evaluate_kit_library({"name": "anything"}, runtime)

    assert payload["family"] == "industrial_crate"
    # parts_for_family_count should align with how many parts allow the family.
    expected = len(kit_parts_for_family(library, "industrial_crate"))
    assert payload["summary"]["parts_for_family_count"] == expected


# ---------------------------------------------------------------------------
# Real fixture conformance
# ---------------------------------------------------------------------------


def test_real_fixtures_validate_against_schema() -> None:
    """Every shipped fixture must pass the in-module validator."""
    library = load_kit_library(_KIT_LIBRARY_BASE)

    assert library.skipped == ()
    # Parity with on-disk file count (best-effort: count *.json files).
    on_disk = sorted(
        path
        for category in REQUIRED_CATEGORIES
        for path in (_KIT_LIBRARY_BASE / category).glob("*.json")
    )
    assert len(on_disk) == len(library.parts)
    # Each loaded part must round-trip through to_dict() without error and
    # carry an internal-license provenance (Phase 12 ships internal-only).
    for part in library.parts:
        as_dict = part.to_dict()
        assert as_dict["provenance"]["license"] == "internal"


def test_real_fixtures_validate_against_jsonschema_dependency() -> None:
    """Defensive: also verify against ``jsonschema`` so a future schema
    drift in either side is detected. Uses the project's pinned
    ``jsonschema`` dependency."""
    import jsonschema  # noqa: PLC0415 - local import keeps test independence

    schema_path = _REPO_ROOT / "schema" / "kit_part.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    for category in REQUIRED_CATEGORIES:
        category_dir = _KIT_LIBRARY_BASE / category
        for fixture_path in sorted(category_dir.glob("*.json")):
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            jsonschema.validate(instance=payload, schema=schema)
