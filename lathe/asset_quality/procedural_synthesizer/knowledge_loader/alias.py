"""FamilyAlias loader — JSON-only, schema-validated at load.

Loads every ``std/procedural/knowledge/aliases/*.json`` file at import
time, validates against ``schemas/alias.schema.json``, and exposes a
lookup by ``family_id``.

A FamilyAlias is the ONLY place where a family name appears in
knowledge data, and it does NOTHING except point at a StyleKnowledge
pack and a list of CompositionPolicy packs. It cannot add structure.
It cannot reference custom code. It is metadata.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .style import KnowledgePackInvalid

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "alias.schema.json"
_KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "std" / "procedural" / "knowledge" / "aliases"


@dataclass(frozen=True)
class FamilyAlias:
    """Pure metadata pointer from family name to (style, policies, domain).

    Cannot add structural nodes. Cannot reference code. Cannot influence
    behavior beyond selecting which style and policy packs the
    synthesizer loads.
    """

    family_id: str
    style_id: str
    policy_ids: tuple[str, ...]
    domain: str
    description: str = ""

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> FamilyAlias:
        return cls(
            family_id=str(raw["family_id"]),
            style_id=str(raw["style_id"]),
            policy_ids=tuple(str(p) for p in raw.get("policy_ids") or ()),
            domain=str(raw["domain"]),
            description=str(raw.get("description") or ""),
        )


def _load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema())


def load_alias_pack(path: Path) -> FamilyAlias:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgePackInvalid(
            f"alias knowledge pack {path} could not be loaded: {exc}"
        ) from exc
    errors = sorted(_validator().iter_errors(raw), key=lambda e: e.path)
    if errors:
        messages = "; ".join(
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        )
        raise KnowledgePackInvalid(
            f"alias knowledge pack {path} failed schema validation: {messages}"
        )
    return FamilyAlias.from_dict(raw)


def load_all_alias_packs(
    root: Path | None = None,
) -> Mapping[str, FamilyAlias]:
    knowledge_root = root or _KNOWLEDGE_ROOT
    if not knowledge_root.exists():
        return {}
    packs: dict[str, FamilyAlias] = {}
    for entry in sorted(knowledge_root.iterdir()):
        if entry.is_dir():
            continue
        if entry.suffix.lower() != ".json":
            raise KnowledgePackInvalid(
                f"non-JSON file in alias knowledge root: {entry}. "
                f"Knowledge packs must be JSON only."
            )
        pack = load_alias_pack(entry)
        if pack.family_id in packs:
            raise KnowledgePackInvalid(
                f"duplicate family_id {pack.family_id!r} in {entry}"
            )
        packs[pack.family_id] = pack
    return packs
