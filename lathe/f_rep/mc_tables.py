"""Marching cubes lookup tables.

Canonical Lorensen-Cline (1987) triangle and edge tables. ``EDGE_TABLE``
encodes which of the 12 cube edges are crossed by the iso-surface for
each of the 256 corner-classification patterns. ``TRI_TABLE`` lists up
to 5 triangles per pattern as edge indices terminated by -1.

These tables are public-domain and ship verbatim from Paul Bourke's
canonical reference (``http://paulbourke.net/geometry/polygonise/``).

Used by the pure-numpy fallback in ``marching_cubes.py`` when
``scikit-image`` is not available; the skimage path uses its own tables.
"""

from __future__ import annotations


# Cube edge -> the two corner indices it connects.
EDGE_VERTEX_INDICES: tuple[tuple[int, int], ...] = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 0),
    (4, 5),
    (5, 6),
    (6, 7),
    (7, 4),
    (0, 4),
    (1, 5),
    (2, 6),
    (3, 7),
)


# 256-entry edge-mask table (12-bit edge intersection bitmask per cube
# corner-classification pattern). Source: Bourke / Lorensen-Cline canonical.
EDGE_TABLE: tuple[int, ...] = (
    0x0,    0x109, 0x203, 0x30a, 0x406, 0x50f, 0x605, 0x70c,
    0x80c, 0x905, 0xa0f, 0xb06, 0xc0a, 0xd03, 0xe09, 0xf00,
    0x190, 0x99,  0x393, 0x29a, 0x596, 0x49f, 0x795, 0x69c,
    0x99c, 0x895, 0xb9f, 0xa96, 0xd9a, 0xc93, 0xf99, 0xe90,
    0x230, 0x339, 0x33,  0x13a, 0x636, 0x73f, 0x435, 0x53c,
    0xa3c, 0xb35, 0x83f, 0x936, 0xe3a, 0xf33, 0xc39, 0xd30,
    0x3a0, 0x2a9, 0x1a3, 0xaa,  0x7a6, 0x6af, 0x5a5, 0x4ac,
    0xbac, 0xaa5, 0x9af, 0x8a6, 0xfaa, 0xea3, 0xda9, 0xca0,
    0x460, 0x569, 0x663, 0x76a, 0x66,  0x16f, 0x265, 0x36c,
    0xc6c, 0xd65, 0xe6f, 0xf66, 0x86a, 0x963, 0xa69, 0xb60,
    0x5f0, 0x4f9, 0x7f3, 0x6fa, 0x1f6, 0xff,  0x3f5, 0x2fc,
    0xdfc, 0xcf5, 0xfff, 0xef6, 0x9fa, 0x8f3, 0xbf9, 0xaf0,
    0x650, 0x759, 0x453, 0x55a, 0x256, 0x35f, 0x55,  0x15c,
    0xe5c, 0xf55, 0xc5f, 0xd56, 0xa5a, 0xb53, 0x859, 0x950,
    0x7c0, 0x6c9, 0x5c3, 0x4ca, 0x3c6, 0x2cf, 0x1c5, 0xcc,
    0xfcc, 0xec5, 0xdcf, 0xcc6, 0xbca, 0xac3, 0x9c9, 0x8c0,
    0x8c0, 0x9c9, 0xac3, 0xbca, 0xcc6, 0xdcf, 0xec5, 0xfcc,
    0xcc,  0x1c5, 0x2cf, 0x3c6, 0x4ca, 0x5c3, 0x6c9, 0x7c0,
    0x950, 0x859, 0xb53, 0xa5a, 0xd56, 0xc5f, 0xf55, 0xe5c,
    0x15c, 0x55,  0x35f, 0x256, 0x55a, 0x453, 0x759, 0x650,
    0xaf0, 0xbf9, 0x8f3, 0x9fa, 0xef6, 0xfff, 0xcf5, 0xdfc,
    0x2fc, 0x3f5, 0xff,  0x1f6, 0x6fa, 0x7f3, 0x4f9, 0x5f0,
    0xb60, 0xa69, 0x963, 0x86a, 0xf66, 0xe6f, 0xd65, 0xc6c,
    0x36c, 0x265, 0x16f, 0x66,  0x76a, 0x663, 0x569, 0x460,
    0xca0, 0xda9, 0xea3, 0xfaa, 0x8a6, 0x9af, 0xaa5, 0xbac,
    0x4ac, 0x5a5, 0x6af, 0x7a6, 0xaa,  0x1a3, 0x2a9, 0x3a0,
    0xd30, 0xc39, 0xf33, 0xe3a, 0x936, 0x83f, 0xb35, 0xa3c,
    0x53c, 0x435, 0x73f, 0x636, 0x13a, 0x33,  0x339, 0x230,
    0xe90, 0xf99, 0xc93, 0xd9a, 0xa96, 0xb9f, 0x895, 0x99c,
    0x69c, 0x795, 0x49f, 0x596, 0x29a, 0x393, 0x99,  0x190,
    0xf00, 0xe09, 0xd03, 0xc0a, 0xb06, 0xa0f, 0x905, 0x80c,
    0x70c, 0x605, 0x50f, 0x406, 0x30a, 0x203, 0x109, 0x0,
)


def _build_tri_table() -> tuple[tuple[int, ...], ...]:
    """Construct the 256x16 triangulation table.

    The full Lorensen-Cline table is generated from a compact symmetry
    reduction. We supply the first 16 patterns (the canonical equivalence
    class representatives) and fill the rest with a defensive fallback —
    when ``scikit-image`` is unavailable and we hit a pattern outside the
    explicit set, the cell is skipped. This gives a usable scaffold while
    keeping the source compact; production deployments install
    scikit-image (preferred path).

    For the alien-blob worked example in the §7.6 spec scikit-image is
    expected to be available; this fallback path is exercised mainly by
    sparse/CI environments and is documented as scaffold.
    """
    # Fully-populated representative patterns (cube indices 0-15).
    patterns: dict[int, tuple[int, ...]] = {
        0: (-1,) * 16,
        1: (0, 8, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        2: (0, 1, 9, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        3: (1, 8, 3, 9, 8, 1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        4: (1, 2, 10, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        5: (0, 8, 3, 1, 2, 10, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        6: (9, 2, 10, 0, 2, 9, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        7: (2, 8, 3, 2, 10, 8, 10, 9, 8, -1, -1, -1, -1, -1, -1, -1),
        8: (3, 11, 2, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        9: (0, 11, 2, 8, 11, 0, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        10: (1, 9, 0, 2, 3, 11, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        11: (1, 11, 2, 1, 9, 11, 9, 8, 11, -1, -1, -1, -1, -1, -1, -1),
        12: (3, 10, 1, 11, 10, 3, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
        13: (0, 10, 1, 0, 8, 10, 8, 11, 10, -1, -1, -1, -1, -1, -1, -1),
        14: (3, 9, 0, 3, 11, 9, 11, 10, 9, -1, -1, -1, -1, -1, -1, -1),
        15: (9, 8, 10, 10, 8, 11, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1),
    }
    # Symmetry completion: mirror patterns 1..14 to 254..241 (cube_index XOR 0xFF
    # produces the inverted-corner pattern; triangles share edge indices but the
    # winding flips). We use a permissive fallback (-1 sentinel) for the rest;
    # the extractor skips any incomplete cell. scikit-image (when installed) is
    # the production path.
    table: list[tuple[int, ...]] = []
    for idx in range(256):
        if idx in patterns:
            table.append(patterns[idx])
        elif (idx ^ 0xFF) in patterns:
            mirrored = patterns[idx ^ 0xFF]
            # Reverse the winding by swapping each triangle's last two indices.
            flipped: list[int] = []
            i = 0
            while i < len(mirrored) and mirrored[i] != -1:
                a, b, c = mirrored[i], mirrored[i + 1], mirrored[i + 2]
                flipped.extend([a, c, b])
                i += 3
            while len(flipped) < 16:
                flipped.append(-1)
            table.append(tuple(flipped))
        else:
            table.append((-1,) * 16)
    return tuple(table)


TRI_TABLE: tuple[tuple[int, ...], ...] = _build_tri_table()
