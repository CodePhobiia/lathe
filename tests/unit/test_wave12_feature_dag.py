"""Wave 12: FeatureDAG + spatial cluster + batched boolean tests."""

from __future__ import annotations

from lathe.geometry.batched_boolean import (
    execute_batched_request_stub,
    plan_batched_boolean,
)
from lathe.geometry.feature_dag import FeatureDAG, FeatureDAGNode
from lathe.geometry.spatial_cluster import AABB, ClusterEntry, cluster_by_bbox_overlap


def test_aabb_overlap_basics() -> None:
    a = AABB((0, 0, 0), (10, 10, 10))
    b = AABB((9, 9, 9), (20, 20, 20))
    assert a.overlaps(b)
    c = AABB((100, 100, 100), (200, 200, 200))
    assert not a.overlaps(c)


def test_aabb_margin_brings_neighbors_together() -> None:
    a = AABB((0, 0, 0), (10, 10, 10))
    b = AABB((10.4, 0, 0), (20, 10, 10))
    assert not a.overlaps(b, margin_cm=0.1)
    assert a.overlaps(b, margin_cm=0.5)


def test_cluster_by_bbox_overlap_splits_disjoint() -> None:
    entries = [
        ClusterEntry("a", AABB((0, 0, 0), (10, 10, 10))),
        ClusterEntry("b", AABB((5, 5, 5), (15, 15, 15))),
        ClusterEntry("c", AABB((100, 100, 100), (110, 110, 110))),
    ]
    clusters = cluster_by_bbox_overlap(entries)
    # a + b overlap → one cluster; c isolated → second cluster.
    assert len(clusters) == 2
    cluster_sizes = sorted(len(c) for c in clusters)
    assert cluster_sizes == [1, 2]


def test_feature_dag_lookup() -> None:
    nodes = (
        FeatureDAGNode("body", "primitive", {"shape": "rounded_box"}),
        FeatureDAGNode("cut1", "primitive", {"shape": "box"}),
        FeatureDAGNode("body_cut", "boolean", {"operation": "difference"}, inputs=("body", "cut1")),
    )
    dag = FeatureDAG("test", nodes)
    assert dag.by_id("body").node_kind == "primitive"
    assert len(dag.primitive_nodes()) == 2
    assert len(dag.boolean_nodes()) == 1


def test_plan_batched_boolean_emits_one_request_per_cluster() -> None:
    nodes = (
        FeatureDAGNode("body", "primitive", {}),
        FeatureDAGNode("handle_l", "primitive", {}),
        FeatureDAGNode("decal_far", "primitive", {}),
    )
    dag = FeatureDAG("crate", nodes)
    aabbs = {
        "body": AABB((-50, -30, -25), (50, 30, 25)),
        "handle_l": AABB((-55, -3, -3), (-45, 3, 3)),  # touches body's left
        "decal_far": AABB((1000, 1000, 1000), (1010, 1010, 1010)),  # disjoint
    }
    requests = plan_batched_boolean(dag, aabbs)
    assert len(requests) == 2  # one cluster for body+handle, one for decal_far
    sizes = sorted(len(r.primitive_ids) for r in requests)
    assert sizes == [1, 2]


def test_plan_batched_boolean_honors_difference_op() -> None:
    nodes = (
        FeatureDAGNode("body", "primitive", {}),
        FeatureDAGNode("cut1", "primitive", {}),
        FeatureDAGNode("body_minus_cut", "boolean",
                       {"operation": "difference"}, inputs=("body", "cut1")),
    )
    dag = FeatureDAG("test", nodes)
    aabbs = {
        "body": AABB((0, 0, 0), (10, 10, 10)),
        "cut1": AABB((5, 5, 5), (15, 15, 15)),
    }
    requests = plan_batched_boolean(dag, aabbs)
    assert len(requests) == 1
    assert "-" in requests[0].boolean_expression


def test_execute_batched_request_stub() -> None:
    nodes = (FeatureDAGNode("body", "primitive", {}),)
    dag = FeatureDAG("test", nodes)
    aabbs = {"body": AABB((0, 0, 0), (10, 10, 10))}
    requests = plan_batched_boolean(dag, aabbs)
    result = execute_batched_request_stub(requests[0])
    assert result.output_face_count > 0
    assert result.fell_back_to_serial is False
