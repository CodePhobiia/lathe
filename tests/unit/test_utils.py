"""Unit tests for ``lathe.utils`` path/merge helpers.

The module is small but load-bearing for resolver/normalizer patch
application. We verify:

* ``dedupe_keep_first`` dedupe order semantics (non-hashable safe)
* ``deep_merge`` overlay precedence and base immutability
* ``get_by_path`` / ``has_path`` happy + missing paths
* ``set_by_path`` / ``unset_by_path`` create-as-you-go and idempotence
* ``append_by_path`` / ``remove_by_path`` list operations + type guards
* ``deep_fill_missing`` only fills holes, never overrides
"""

from __future__ import annotations

import unittest

from lathe.utils import (
    append_by_path,
    dedupe_keep_first,
    deep_fill_missing,
    deep_merge,
    get_by_path,
    has_path,
    remove_by_path,
    set_by_path,
    unset_by_path,
)


class DedupeKeepFirstTests(unittest.TestCase):
    def test_preserves_first_occurrence_order(self) -> None:
        self.assertEqual(dedupe_keep_first(["a", "b", "a", "c", "b"]), ["a", "b", "c"])

    def test_handles_unhashable_dicts(self) -> None:
        out = dedupe_keep_first([{"x": 1}, {"x": 1}, {"x": 2}])
        self.assertEqual(out, [{"x": 1}, {"x": 2}])

    def test_empty_input_returns_empty_list(self) -> None:
        self.assertEqual(dedupe_keep_first([]), [])


class DeepMergeTests(unittest.TestCase):
    def test_overlay_overrides_scalar(self) -> None:
        self.assertEqual(deep_merge({"a": 1}, {"a": 2}), {"a": 2})

    def test_recursively_merges_nested_dicts(self) -> None:
        merged = deep_merge({"a": {"x": 1, "y": 2}}, {"a": {"y": 9, "z": 3}})
        self.assertEqual(merged, {"a": {"x": 1, "y": 9, "z": 3}})

    def test_does_not_mutate_inputs(self) -> None:
        base = {"a": {"x": 1}}
        overlay = {"a": {"y": 2}}
        deep_merge(base, overlay)
        self.assertEqual(base, {"a": {"x": 1}})
        self.assertEqual(overlay, {"a": {"y": 2}})


class PathAccessorTests(unittest.TestCase):
    def test_get_by_path_descends_into_nested_dicts(self) -> None:
        data = {"a": {"b": {"c": 42}}}
        self.assertEqual(get_by_path(data, "a.b.c"), 42)

    def test_get_by_path_raises_keyerror_when_missing(self) -> None:
        with self.assertRaises(KeyError):
            get_by_path({"a": {}}, "a.b.c")

    def test_has_path_distinguishes_present_vs_missing(self) -> None:
        data = {"a": {"b": {"c": 1}}}
        self.assertTrue(has_path(data, "a.b.c"))
        self.assertFalse(has_path(data, "a.b.d"))
        self.assertFalse(has_path(data, "a.x.y"))

    def test_set_by_path_creates_intermediate_dicts(self) -> None:
        data: dict = {}
        set_by_path(data, "a.b.c", 7)
        self.assertEqual(data, {"a": {"b": {"c": 7}}})

    def test_unset_by_path_removes_leaf_and_is_idempotent(self) -> None:
        data = {"a": {"b": 1}}
        unset_by_path(data, "a.b")
        self.assertEqual(data, {"a": {}})
        unset_by_path(data, "a.b")  # missing — should be a no-op
        unset_by_path(data, "x.y.z")  # missing intermediate — also no-op
        self.assertEqual(data, {"a": {}})


class ListPathTests(unittest.TestCase):
    def test_append_by_path_appends_scalars_and_extends_lists(self) -> None:
        data = {"items": [1, 2]}
        append_by_path(data, "items", 3)
        self.assertEqual(data["items"], [1, 2, 3])
        append_by_path(data, "items", [4, 5])
        self.assertEqual(data["items"], [1, 2, 3, 4, 5])

    def test_append_by_path_rejects_non_list_target(self) -> None:
        with self.assertRaises(TypeError):
            append_by_path({"items": "not-a-list"}, "items", "x")

    def test_remove_by_path_filters_matching_values(self) -> None:
        data = {"items": [1, 2, 3, 2]}
        remove_by_path(data, "items", 2)
        self.assertEqual(data["items"], [1, 3])

    def test_remove_by_path_rejects_non_list_target(self) -> None:
        with self.assertRaises(TypeError):
            remove_by_path({"items": {"x": 1}}, "items", "x")


class DeepFillMissingTests(unittest.TestCase):
    def test_fills_missing_keys_only(self) -> None:
        target = {"a": 1, "nested": {"x": 1}}
        defaults = {"a": 99, "b": 2, "nested": {"x": 99, "y": 5}}
        out = deep_fill_missing(target, defaults)
        # existing scalars preserved, missing scalars filled
        self.assertEqual(out["a"], 1)
        self.assertEqual(out["b"], 2)
        # nested existing preserved, nested missing filled
        self.assertEqual(out["nested"], {"x": 1, "y": 5})

    def test_does_not_mutate_target(self) -> None:
        target = {"a": 1}
        deep_fill_missing(target, {"a": 9, "b": 2})
        self.assertEqual(target, {"a": 1})


if __name__ == "__main__":
    unittest.main()
