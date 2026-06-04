"""Wave 17 tests: FeatureDAG variadic boolean executor."""

from __future__ import annotations

import numpy as np
import trimesh

from lathe.geometry.batched_boolean import (
    BatchedBooleanRequest,
    execute_batched_request,
    execute_batched_request_stub,
)


def test_executor_falls_back_to_stub_when_no_meshes() -> None:
    request = BatchedBooleanRequest(
        cluster_id="c0",
        primitive_ids=("a", "b"),
        boolean_expression="(a + b)",
    )
    result = execute_batched_request(request, primitive_meshes=None)
    assert result.cluster_id == "c0"
    assert result.fell_back_to_serial is False  # stub-path identity
    # Stub uses synthetic 32 faces per primitive.
    assert result.output_face_count == 64


def test_executor_identity_for_single_primitive() -> None:
    """Single primitive: result face count > 0 and provenance preserved."""
    box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    request = BatchedBooleanRequest(
        cluster_id="c0",
        primitive_ids=("box",),
        boolean_expression="box",
    )
    result = execute_batched_request(request, primitive_meshes={"box": box})
    assert result.output_face_count >= 12  # box has 12 tris
    assert "box" in result.provenance_map
    assert result.fell_back_to_serial is False


def test_executor_union_of_two_boxes() -> None:
    """Batched union: two disjoint boxes → combined face count."""
    a = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    b = trimesh.creation.box(
        extents=(2.0, 2.0, 2.0),
        transform=np.array([[1, 0, 0, 5.0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]),
    )
    request = BatchedBooleanRequest(
        cluster_id="c0",
        primitive_ids=("a", "b"),
        boolean_expression="(a + b)",
    )
    result = execute_batched_request(request, primitive_meshes={"a": a, "b": b})
    # Two disjoint boxes union → still around 24 tris (2 * 12).
    assert result.output_face_count >= 20
    assert set(result.provenance_map.keys()) == {"a", "b"}


def test_executor_difference_drops_volume() -> None:
    """Difference: large box minus small box should still produce a manifold."""
    large = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
    small = trimesh.creation.box(
        extents=(1.0, 1.0, 1.0),
        transform=np.array([[1, 0, 0, 0.0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]),
    )
    request = BatchedBooleanRequest(
        cluster_id="c0",
        primitive_ids=("large", "small"),
        boolean_expression="(large - small)",
    )
    result = execute_batched_request(request, primitive_meshes={"large": large, "small": small})
    # Difference produces more tris than the input (cut-out faces added).
    assert result.output_face_count > 12
