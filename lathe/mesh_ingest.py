"""Safe mesh-ingest wrapper (SEC-2 + SEC-NEW-1).

``safe_load_mesh`` wraps :func:`trimesh.load` with a size cap, format
allowlist, magic-byte sniff, and post-load sanity checks. It raises
:class:`ShapeMeshLoadError` on any violation so callers see a single,
narrow exception class instead of the wide exception surface of the
underlying loader.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np
import trimesh

from .errors import ShapeMeshLoadError
from .security import InputClass, TrustLevel, boundary_policy, ingress_boundary

# trimesh's public load-failure class moved between versions; fall back
# to ``Exception`` at the narrowest if the attribute is missing. We still
# catch the specific stdlib classes alongside.
_TRIMESH_LOAD_EXC: tuple[type[BaseException], ...] = tuple(
    cls for cls in (getattr(trimesh.exceptions, "LoadError", None),) if cls is not None
)


ALLOWED_MESH_FORMATS = frozenset({".glb", ".gltf", ".obj", ".off", ".ply", ".stl"})
DEFAULT_MAX_BYTES = 256 * 1024 * 1024  # 256 MiB
_MAX_FACES = 5_000_000
_MAX_VERTICES = 5_000_000

_PROVIDER_ID = "lathe.mesh_ingest"
_MESH_INGEST_BOUNDARY = boundary_policy(
    name="external_mesh_ingest",
    input_class=InputClass.EXTERNAL_MESH,
    trust_level=TrustLevel.UNTRUSTED,
    controls=(
        "format_allowlist",
        "byte_cap",
        "magic_byte_sniff",
        "trimesh_exception_narrowing",
        "post_load_sanity",
    ),
)


def _raise(code: str, **details) -> None:
    raise ShapeMeshLoadError(
        _PROVIDER_ID,
        f"mesh ingest rejected: {code}",
        code=code,
        details=details,
    )


def _sniff_magic(path: Path, ext: str, filesize: int) -> None:
    with path.open("rb") as fh:
        prefix = fh.read(16)

    if ext == ".glb":
        if not prefix.startswith(b"glTF"):
            _raise("magic_mismatch", ext=ext, actual_prefix=prefix[:4].hex())
        return

    if ext == ".gltf":
        # gltf is JSON; require an ASCII-printable first byte.
        if not prefix or prefix[0] > 0x7E or prefix[0] < 0x20:
            _raise("magic_mismatch", ext=ext, actual_prefix=prefix[:4].hex())
        return

    if ext == ".obj":
        if not prefix:
            _raise("magic_mismatch", ext=ext, actual_prefix="")
        first = prefix[0]
        if first < 0x20 or first > 0x7E:
            _raise("magic_mismatch", ext=ext, actual_prefix=prefix[:4].hex())
        return

    if ext == ".off":
        if not prefix.startswith(b"OFF") and not prefix.startswith(b"COFF"):
            _raise("magic_mismatch", ext=ext, actual_prefix=prefix[:4].hex())
        return

    if ext == ".ply":
        if not (prefix.startswith(b"ply\n") or prefix.startswith(b"ply\r")):
            _raise("magic_mismatch", ext=ext, actual_prefix=prefix[:4].hex())
        return

    if ext == ".stl":
        if prefix.startswith(b"solid "):
            return
        # Binary STL: 80-byte header + uint32 face count, total size
        # should equal header + 4 + count * 50.
        if filesize < 84:
            _raise("magic_mismatch", ext=ext, actual_prefix=prefix[:4].hex())
        with path.open("rb") as fh:
            fh.seek(80)
            count_bytes = fh.read(4)
        if len(count_bytes) != 4:
            _raise("magic_mismatch", ext=ext, actual_prefix=prefix[:4].hex())
        (face_count,) = struct.unpack("<I", count_bytes)
        expected = 84 + face_count * 50
        if expected > filesize:
            _raise(
                "magic_mismatch",
                ext=ext,
                face_count=face_count,
                expected=expected,
                filesize=filesize,
            )
        return

    # Unreachable — allowed_formats guards this.
    _raise("magic_mismatch", ext=ext, actual_prefix=prefix[:4].hex())


def _post_load_sanity(mesh: trimesh.Trimesh) -> None:
    faces = getattr(mesh, "faces", None)
    vertices = getattr(mesh, "vertices", None)
    if faces is None or vertices is None:
        _raise("post_load_sanity", field="shape", detail="missing faces/vertices")

    if len(faces) > _MAX_FACES:
        _raise("post_load_sanity", field="faces", detail=f"{len(faces)}>{_MAX_FACES}")
    if len(vertices) > _MAX_VERTICES:
        _raise(
            "post_load_sanity",
            field="vertices",
            detail=f"{len(vertices)}>{_MAX_VERTICES}",
        )

    arr = np.asarray(vertices, dtype=float)
    if arr.size and not np.isfinite(arr).all():
        _raise("post_load_sanity", field="vertices", detail="non-finite coordinate")

    bounds = getattr(mesh, "bounds", None)
    if bounds is not None:
        bounds_arr = np.asarray(bounds, dtype=float)
        if bounds_arr.size and not np.isfinite(bounds_arr).all():
            _raise("post_load_sanity", field="bounds", detail="non-finite bound")


@ingress_boundary(_MESH_INGEST_BOUNDARY)
def safe_load_mesh(
    path: Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    allowed_formats: frozenset[str] = ALLOWED_MESH_FORMATS,
) -> trimesh.Trimesh:
    """Load a mesh safely with size, format, magic, and sanity guards.

    Args:
        path: Filesystem path to mesh artifact.
        max_bytes: Maximum file size (bytes). Default 256 MiB.
        allowed_formats: Extensions allowed (lowercase, with dot).

    Returns:
        Loaded :class:`trimesh.Trimesh`.

    Raises:
        ShapeMeshLoadError: On any violation.
    """
    path = Path(path)
    try:
        filesize = path.stat().st_size
    except OSError as exc:
        raise ShapeMeshLoadError(
            _PROVIDER_ID,
            f"cannot stat mesh: {path}",
            code="stat_failed",
            details={"error": type(exc).__name__},
        ) from exc

    if filesize > max_bytes:
        _raise("oversized", actual=filesize, limit=max_bytes)

    ext = path.suffix.lower()
    if ext not in allowed_formats:
        _raise("format_disallowed", ext=ext)

    _sniff_magic(path, ext, filesize)

    try:
        loaded = trimesh.load(path, force="mesh", process=False)
    except (
        OSError,
        ValueError,
        KeyError,
        IndexError,
        NotImplementedError,
        AttributeError,
        TypeError,
        UnicodeDecodeError,
        *_TRIMESH_LOAD_EXC,
    ) as exc:
        raise ShapeMeshLoadError(
            _PROVIDER_ID,
            f"trimesh load failed: {path}",
            code="trimesh_error",
            details={"ext": ext, "exc_class": type(exc).__name__},
        ) from exc

    if not isinstance(loaded, trimesh.Trimesh):
        _raise("trimesh_error", ext=ext, exc_class="NotATrimesh")

    _post_load_sanity(loaded)
    return loaded


__all__ = [
    "ALLOWED_MESH_FORMATS",
    "DEFAULT_MAX_BYTES",
    "safe_load_mesh",
]

# Silence unused-import warnings for math (kept for future NaN helpers).
_ = math
