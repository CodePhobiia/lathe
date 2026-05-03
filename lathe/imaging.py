"""Pillow ingress helpers with decompression-bomb protection.

``Image.open`` issues ``Image.DecompressionBombWarning`` for images larger
than ``PIL.Image.MAX_IMAGE_PIXELS``. By default that warning is *non-fatal*
— Pillow proceeds to decode the image. Every Lathe site that opens an
image should promote that warning to an error so a hostile / malformed
asset cannot exhaust memory or stall the pipeline.

The reference for this pattern lives in
``lathe/shape/geometry/conditioning.py`` (the conditioning stage); this
module hoists the same idiom to a single helper so every Image.open
callsite shares one defense.
"""

from __future__ import annotations

import warnings
from contextlib import contextmanager
from pathlib import Path
from typing import IO, Iterator

from PIL import Image

__all__ = ["bomb_guarded", "open_guarded"]


@contextmanager
def bomb_guarded() -> Iterator[None]:
    """Promote ``Image.DecompressionBombWarning`` to an error inside a block."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        yield


def open_guarded(source: str | Path | IO[bytes]) -> Image.Image:
    """Open an image with decompression-bomb protection.

    Equivalent to :func:`PIL.Image.open` but raises
    :class:`PIL.Image.DecompressionBombError` when the input declares
    dimensions larger than ``Image.MAX_IMAGE_PIXELS``.
    """
    with bomb_guarded():
        return Image.open(source)
