"""Property-based tests for ``lathe.exact_solids``.

The plan lists three transform-theoretic properties (composition
associativity, invertibility, translate-inverse), but ``exact_solids``
does not expose a ``Transform`` abstraction. What it DOES expose is
translation-equivalent primitive construction (``_translated_box``,
``_translated_cylinder``) and ``trimesh.transformations.rotation_matrix``-
based axis reorientation. We adapt the plan to the module's actual
surface:

- Transform composition associativity (on translations): composing
  translate(v1) ∘ translate(v2) ∘ translate(v3) yields the same mesh
  regardless of grouping — translations form an associative group on
  ``trimesh.Trimesh``.
- Transform invertibility: translate by +v then −v restores the origin
  mesh to within ``1e-6`` tolerance.
- Translate-then-translate-inverse on ``_translated_box`` recovers the
  canonical centered box — translation is invertible on the primitive
  constructor too.

All properties exercised via ``pytest.mark.parametrize`` (hypothesis
unavailable).
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from lathe.exact_solids import _translated_box, _translated_cylinder


TRANSLATION_TRIPLES = [
    pytest.param(
        (np.array([1.0, 0.0, 0.0]), np.array([0.0, 2.0, 0.0]), np.array([0.0, 0.0, 3.0])),
        id="axis_aligned_unit_triple",
    ),
    pytest.param(
        (np.array([1.5, -1.5, 0.0]), np.array([-0.5, 2.5, -1.0]), np.array([0.0, 0.0, 4.0])),
        id="mixed_signs_triple",
    ),
    pytest.param(
        (np.array([10.0, 10.0, 10.0]), np.array([-5.0, -5.0, -5.0]), np.array([2.0, 2.0, 2.0])),
        id="large_magnitude_triple",
    ),
    pytest.param(
        (np.array([0.1, 0.2, 0.3]), np.array([0.3, 0.2, 0.1]), np.array([-0.2, -0.1, -0.3])),
        id="small_magnitude_triple",
    ),
    pytest.param(
        (np.array([0.0, 0.0, 0.0]), np.array([5.0, 5.0, 5.0]), np.array([-2.0, 3.0, 1.0])),
        id="with_zero_vector",
    ),
]


def _apply_translation(mesh: trimesh.Trimesh, vector: np.ndarray) -> trimesh.Trimesh:
    copy = mesh.copy()
    copy.apply_translation(vector)
    return copy


@pytest.mark.parametrize("triple", TRANSLATION_TRIPLES)
def test_translate_composition_is_associative(triple: tuple[np.ndarray, np.ndarray, np.ndarray]) -> None:
    """(A ∘ B) ∘ C == A ∘ (B ∘ C) on translations applied to a mesh — the
    two grouping orders produce identical vertex arrays (translation is
    associative).
    """
    v1, v2, v3 = triple
    base = trimesh.creation.box(extents=(2.0, 2.0, 2.0))

    # (v1 then v2) then v3
    left = _apply_translation(_apply_translation(_apply_translation(base, v1), v2), v3)
    # v1 then (v2 then v3)  — we can build the same end state by
    # stepping each translation individually in the same overall order,
    # which is the associativity invariant applied to translations.
    # To differentiate grouping, pre-compose v2+v3 as a single vector:
    right = _apply_translation(_apply_translation(base, v1), v2 + v3)
    assert np.allclose(left.vertices, right.vertices, atol=1e-9)


@pytest.mark.parametrize(
    "vector",
    [
        pytest.param(np.array([1.0, 0.0, 0.0]), id="pos_x"),
        pytest.param(np.array([-2.0, 3.0, -4.0]), id="mixed_sign"),
        pytest.param(np.array([100.0, 100.0, 100.0]), id="large_pos"),
        pytest.param(np.array([0.001, 0.002, 0.003]), id="small_pos"),
        pytest.param(np.array([0.0, 0.0, 0.0]), id="zero_vector"),
    ],
)
def test_translate_is_invertible_within_tolerance(vector: np.ndarray) -> None:
    """Translating by +v then −v restores the original mesh to within
    1e-6 tolerance. Translation is its own inverse under negation.
    """
    base = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    roundtrip = _apply_translation(_apply_translation(base, vector), -vector)
    assert np.allclose(roundtrip.vertices, base.vertices, atol=1e-6)


@pytest.mark.parametrize(
    "center",
    [
        pytest.param((1.0, 0.0, 0.0), id="center_x"),
        pytest.param((0.0, 2.0, 0.0), id="center_y"),
        pytest.param((0.0, 0.0, 3.0), id="center_z"),
        pytest.param((1.5, -2.5, 4.0), id="center_mixed"),
        pytest.param((0.0, 0.0, 0.0), id="origin"),
    ],
)
def test_translated_box_translate_inverse_restores_origin(center: tuple[float, float, float]) -> None:
    """_translated_box at `center`, shifted by −center, must sit centered
    at the origin — the primitive constructor's translation is invertible.
    """
    extents = (2.0, 2.0, 2.0)
    box = _translated_box(extents, center)
    box.apply_translation(-np.asarray(center, dtype=np.float64))
    bmin, bmax = box.bounds
    midpoint = (bmin + bmax) / 2.0
    assert np.allclose(midpoint, [0.0, 0.0, 0.0], atol=1e-9)
    assert np.allclose(bmax - bmin, extents, atol=1e-9)


@pytest.mark.parametrize(
    "axis",
    [
        pytest.param("x", id="axis_x"),
        pytest.param("y", id="axis_y"),
        pytest.param("z", id="axis_z"),
    ],
)
@pytest.mark.parametrize(
    "center",
    [
        pytest.param((0.0, 0.0, 0.0), id="origin"),
        pytest.param((1.0, 2.0, 3.0), id="offset"),
    ],
)
def test_translated_cylinder_translate_inverse_restores_origin(axis: str, center: tuple[float, float, float]) -> None:
    """_translated_cylinder at `center`, shifted by −center, recovers a
    cylinder whose bounding-box midpoint is at the origin. Construction
    translation is invertible for cylinders regardless of axis.
    """
    cyl = _translated_cylinder(radius=0.5, height=2.0, center=center, axis=axis)
    cyl.apply_translation(-np.asarray(center, dtype=np.float64))
    bmin, bmax = cyl.bounds
    midpoint = (bmin + bmax) / 2.0
    # Cylinder midpoint lands on the origin after the inverse translation.
    assert np.allclose(midpoint, [0.0, 0.0, 0.0], atol=1e-6)
