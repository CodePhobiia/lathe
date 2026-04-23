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
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
