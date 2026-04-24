"""Random-number generation helpers keyed off the asset seed.

Extracted from ``lathe/executor.py`` during Stage 2.IV per Plan 01 Phase 7
(``RNG_PRIME_OFFSET`` already lives in ``lathe.constants``; we just need the
stage-facing helper to import it from that canonical location).
"""

from __future__ import annotations

import numpy as np

from ..constants import RNG_PRIME_OFFSET


def candidate_rng(seed: int, index: int) -> np.random.Generator:
    """Candidate rng.

    Args:
        seed: seed argument.
        index: index argument.

    Returns:
        The result.
    """
    return np.random.default_rng(seed + index * RNG_PRIME_OFFSET)
