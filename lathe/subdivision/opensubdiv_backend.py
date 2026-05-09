"""Optional OpenSubDiv backend with deterministic CPU fallback.

We treat OpenSubDiv as an *opt-in* refinement; the CPU implementation
(:mod:`.catmull_clark`, :mod:`.loop`) is the reference runtime that
hero builds use by default. If the user installs ``pyopensubdiv`` (or
the Pixar-shipped ``OpenSubdiv`` Python module) we delegate the
refinement step to that library so studios with an optimised native
build can use the same authoring surface; otherwise we fall through
to the CPU path with an explicit attempted/actual provenance record
mirroring the rest of the Lathe runtime (see CLAUDE.md "When a provider
falls back, the trace records both the attempted and the actual
provider").

The native backend integration is intentionally a thin proposal: the
goal of this scaffold is to keep the contract surface honest and the
authoring API stable. The actual ``pyopensubdiv`` glue lives behind a
runtime check so the import never trips on machines without the C++
library.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .boundary import BoundaryRule
from .creases import CreaseTags
from .scheme import SubdivisionScheme

if TYPE_CHECKING:
    from .mesh import SubdivMesh


@dataclass(frozen=True)
class OpenSubDivAvailability:
    """Runtime probe result for the OpenSubDiv backend."""

    available: bool
    module_name: str | None
    version: str | None
    reason: str | None


def opensubdiv_availability() -> OpenSubDivAvailability:
    """Detect whether an OpenSubDiv Python binding is importable.

    The probe checks ``pyopensubdiv`` first (community wheel) then the
    Pixar-shipped ``OpenSubdiv`` namespace. Detection is best-effort and
    must never raise: failure cases all return ``available=False`` with
    a human-readable reason.
    """
    for module_name in ("pyopensubdiv", "OpenSubdiv"):
        try:
            module = __import__(module_name)
        except Exception as exc:  # pragma: no cover - defensive
            last_reason = f"{module_name}: {exc}"
            continue
        version = getattr(module, "__version__", None) or getattr(
            module, "version", None
        )
        return OpenSubDivAvailability(
            available=True,
            module_name=module_name,
            version=str(version) if version else None,
            reason=None,
        )
    return OpenSubDivAvailability(
        available=False,
        module_name=None,
        version=None,
        reason="pyopensubdiv / OpenSubdiv import failed; CPU fallback in use",
    )


def subdivide_via_opensubdiv(
    mesh: "SubdivMesh",
    *,
    scheme: SubdivisionScheme,
    levels: int,
    creases: CreaseTags,
    boundary: BoundaryRule,
) -> "SubdivMesh":
    """Refine ``mesh`` via OpenSubDiv when the native binding is present.

    The current implementation is a deterministic *passthrough*: when
    the optional binding is importable we still call into the CPU
    refinement so behaviour stays bit-for-bit reproducible across
    machines. A future change can replace the body with a true native
    refinement once the topology-refiner glue is wired up; the
    contract surface above is the public extension point.
    """
    # Local import keeps the heavy cycle (algorithm <-> backend) confined
    # to the call path rather than the module load path.
    from .catmull_clark import subdivide_catmull_clark
    from .loop import subdivide_loop

    current = mesh
    levels = max(0, int(levels))
    active = creases
    for _ in range(levels):
        if scheme is SubdivisionScheme.CATMULL_CLARK:
            current = subdivide_catmull_clark(
                current, creases=active, boundary=boundary
            )
        elif scheme is SubdivisionScheme.LOOP:
            current = subdivide_loop(
                current, creases=active, boundary=boundary
            )
        else:
            raise ValueError(f"unsupported subdivision scheme: {scheme}")
        active = active.attenuate()
    return current


__all__ = [
    "OpenSubDivAvailability",
    "opensubdiv_availability",
    "subdivide_via_opensubdiv",
]
