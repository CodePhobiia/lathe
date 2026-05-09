"""OpenSubDiv-class finishing pass for Lathe (roadmap §7.5).

Public, dependency-light surface-subdivision module that converts a
low-poly *cage* into a high-poly *subdivision surface*. Implements

* :class:`SubdivMesh`        --- minimal indexed-face mesh used by the
  subdivision algorithms; tolerates mixed quad/triangle/n-gon faces.
* :class:`CreaseTags`        --- author-declared per-edge sharpness;
  semi-sharp creases interpolate between smooth and infinitely-sharp.
* :class:`BoundaryRule`      --- boundary edge handling (smooth corner
  vs. crease-equivalent).
* :func:`subdivide_catmull_clark` / :func:`subdivide_loop` -- pure-Python
  subdivision schemes (numpy used only for vector arithmetic).
* :func:`subdivide_mesh`     --- scheme-dispatching entry point honouring
  ``levels`` and crease tags.
* :func:`apply_finishing`    --- runs the subdivision finishing pass
  declared by an asset's ``geometry.subdivision`` block (or the legacy
  ``subdivision_finishing`` decl) on a runtime mesh, returning the
  refined mesh and a deterministic report.
* :func:`from_geometry_block` --- parse a subdivision block out of a
  normalised asset record.

The CPU implementation is the *reference* runtime. An optional
:mod:`lathe.subdivision.opensubdiv_backend` falls back to the CPU
scheme when ``pyopensubdiv``/``OpenSubdiv`` is not importable so that
hero builds remain deterministic without external libraries.

The whole module is deterministic: face/vertex iteration is index-ordered
and floating point arithmetic uses double precision. No randomness, no
floating-point hashing, no thread-locals.
"""

from __future__ import annotations

from .boundary import BoundaryRule, classify_boundary_edges
from .catmull_clark import subdivide_catmull_clark
from .creases import CreaseTags, normalise_crease_sharpness
from .from_geometry import (
    SubdivisionFinishingSpec,
    WorkedChestLidExample,
    apply_finishing,
    from_geometry_block,
    hero_default_spec,
)
from .loop import subdivide_loop
from .mesh import SubdivMesh, mesh_from_arrays, mesh_to_arrays
from .opensubdiv_backend import (
    OpenSubDivAvailability,
    opensubdiv_availability,
    subdivide_via_opensubdiv,
)
from .scheme import SubdivisionScheme, parse_scheme
from .validator import SubdivisionValidationError, validate_for_subdivision


def subdivide_mesh(
    mesh: SubdivMesh,
    *,
    scheme: SubdivisionScheme | str = SubdivisionScheme.CATMULL_CLARK,
    levels: int = 1,
    creases: CreaseTags | None = None,
    boundary: BoundaryRule | str = BoundaryRule.SMOOTH,
    backend: str = "auto",
) -> SubdivMesh:
    """Subdivide ``mesh`` ``levels`` times using ``scheme``.

    ``backend='auto'`` first tries :mod:`opensubdiv_backend`; if the C++
    library is not importable it falls through to the CPU reference
    implementation. ``backend='cpu'`` forces the CPU path. Determinism
    contract: identical inputs produce identical outputs across both
    backends bit-for-bit, because the OpenSubDiv backend is currently a
    stub that delegates to the CPU implementation.
    """
    parsed_scheme = parse_scheme(scheme)
    boundary_rule = (
        boundary
        if isinstance(boundary, BoundaryRule)
        else BoundaryRule(boundary)
    )
    creases = creases or CreaseTags.empty()
    levels = max(0, int(levels))
    if levels == 0:
        return mesh.copy()

    if backend == "opensubdiv":
        return subdivide_via_opensubdiv(
            mesh,
            scheme=parsed_scheme,
            levels=levels,
            creases=creases,
            boundary=boundary_rule,
        )
    if backend == "auto":
        availability = opensubdiv_availability()
        if availability.available:
            return subdivide_via_opensubdiv(
                mesh,
                scheme=parsed_scheme,
                levels=levels,
                creases=creases,
                boundary=boundary_rule,
            )

    current = mesh
    for _ in range(levels):
        if parsed_scheme is SubdivisionScheme.CATMULL_CLARK:
            current = subdivide_catmull_clark(
                current, creases=creases, boundary=boundary_rule
            )
        elif parsed_scheme is SubdivisionScheme.LOOP:
            current = subdivide_loop(
                current, creases=creases, boundary=boundary_rule
            )
        else:
            raise ValueError(f"unsupported subdivision scheme: {parsed_scheme}")
        creases = creases.attenuate()
    return current


__all__ = [
    "BoundaryRule",
    "CreaseTags",
    "OpenSubDivAvailability",
    "SubdivMesh",
    "SubdivisionFinishingSpec",
    "SubdivisionScheme",
    "SubdivisionValidationError",
    "WorkedChestLidExample",
    "apply_finishing",
    "classify_boundary_edges",
    "from_geometry_block",
    "hero_default_spec",
    "mesh_from_arrays",
    "mesh_to_arrays",
    "normalise_crease_sharpness",
    "opensubdiv_availability",
    "parse_scheme",
    "subdivide_catmull_clark",
    "subdivide_loop",
    "subdivide_mesh",
    "subdivide_via_opensubdiv",
    "validate_for_subdivision",
]
