"""StyleKnowledge loader — JSON-only, schema-validated at load.

Loads every ``std/procedural/knowledge/style/*.json`` file once at
import time, validates each against ``schemas/style.schema.json``,
freezes them into ``StyleKnowledge`` instances, and exposes a lookup
by ``style_id``.

A pack that fails schema validation raises ``KnowledgePackInvalid`` at
import time. The synthesizer refuses to start with invalid packs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


_SCHEMA_PATH = Path(__file__).parent / "schemas" / "style.schema.json"
_KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "std" / "procedural" / "knowledge" / "style"


class KnowledgePackInvalid(RuntimeError):
    """Raised when a knowledge file fails schema validation."""


@dataclass(frozen=True)
class StyleKnowledge:
    """Declarative parameter bias for generators. Never adds structure.

    Frozen, immutable. No callables. The synthesizer consumes
    StyleKnowledge as suggested defaults — generators read their
    declared style fields from a pack only when authored intent does
    not pin the value.
    """

    style_id: str
    style_band: str
    proportion_priors: Mapping[str, Mapping[str, float]]
    silhouette_priors: Mapping[str, float]
    density_priors: Mapping[str, Mapping[str, float]]
    parameter_priors: Mapping[str, Mapping[str, Any]]
    description: str = ""

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "StyleKnowledge":
        return cls(
            style_id=str(raw["style_id"]),
            style_band=str(raw["style_band"]),
            proportion_priors=_freeze_two_level(raw.get("proportion_priors", {})),
            silhouette_priors=_freeze_one_level(raw.get("silhouette_priors", {})),
            density_priors=_freeze_two_level(raw.get("density_priors", {})),
            parameter_priors=_freeze_two_level(raw.get("parameter_priors", {})),
            description=str(raw.get("description") or ""),
        )


def _freeze_one_level(value: Any) -> Mapping[str, float]:
    if not isinstance(value, dict):
        return {}
    return {str(k): float(v) for k, v in value.items()}


def _freeze_two_level(value: Any) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {str(k): dict(inner) for k, inner in value.items() if isinstance(inner, dict)}


def _load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema())


def load_style_pack(path: Path) -> StyleKnowledge:
    """Load and validate a single style JSON file.

    Raises ``KnowledgePackInvalid`` if the file fails schema validation
    or cannot be parsed.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgePackInvalid(
            f"style knowledge pack {path} could not be loaded: {exc}"
        ) from exc
    errors = sorted(_validator().iter_errors(raw), key=lambda e: e.path)
    if errors:
        messages = "; ".join(
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        )
        raise KnowledgePackInvalid(
            f"style knowledge pack {path} failed schema validation: {messages}"
        )
    return StyleKnowledge.from_dict(raw)


def load_all_style_packs(
    root: Path | None = None,
) -> Mapping[str, StyleKnowledge]:
    """Discover and load every JSON style pack under ``root``.

    Default root is ``std/procedural/knowledge/style/`` at the
    repository top level. Non-JSON files in the directory raise
    ``KnowledgePackInvalid`` to enforce the data-only constraint.
    """
    knowledge_root = root or _KNOWLEDGE_ROOT
    if not knowledge_root.exists():
        return {}
    packs: dict[str, StyleKnowledge] = {}
    for entry in sorted(knowledge_root.iterdir()):
        if entry.is_dir():
            continue
        if entry.suffix.lower() != ".json":
            raise KnowledgePackInvalid(
                f"non-JSON file in style knowledge root: {entry}. "
                f"Knowledge packs must be JSON only; remove or move "
                f"this file."
            )
        pack = load_style_pack(entry)
        if pack.style_id in packs:
            raise KnowledgePackInvalid(
                f"duplicate style_id {pack.style_id!r} in {entry} "
                f"(already loaded from another file)"
            )
        packs[pack.style_id] = pack
    return packs
