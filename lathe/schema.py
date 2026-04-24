"""Runtime access to the canonical JSON schema.

Loads ``schema/lathe.schema.json`` and exposes helpers that tests and
the checker use to validate normalized ASTs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _find_schema_path() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "schema" / "lathe.schema.json"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Could not locate schema/lathe.schema.json")


SCHEMA_PATH = _find_schema_path()


def get_schema() -> dict[str, Any]:
    # JSON ingress — internal controlled payload from schema/lathe.schema.json canonical schema shipped inside this repo; safe without schema validation (this IS the schema).
    """Get schema.

    Returns:
        The result.
    """
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
