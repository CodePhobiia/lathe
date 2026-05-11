"""CompositionPolicy loader — JSON-only, schema-validated at load.

Loads every ``std/procedural/knowledge/policy/*.json`` file once at
import time, validates against ``schemas/policy.schema.json``, freezes
them into ``CompositionPolicy`` instances, and exposes a lookup by
``policy_id``.

A pack that fails schema validation raises ``KnowledgePackInvalid`` at
import time. The synthesizer refuses to start with invalid packs.

CompositionPolicy is reusable across families. Its precondition matches
on authored intent (NODE_TYPES present, brief fields, parts list,
intent tags) — NEVER on family name. This is the structural foundation
of "procedural, not family-recipes-in-data."
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .style import KnowledgePackInvalid


_SCHEMA_PATH = Path(__file__).parent / "schemas" / "policy.schema.json"
_KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "std" / "procedural" / "knowledge" / "policy"


@dataclass(frozen=True)
class PolicyPrecondition:
    """Pure-data predicate over authored intent. No callables.

    The policy applies when ALL of:
      - every requires_node_types is present in the graph (≥ 1 each)
      - none of forbids_node_types is present
      - every requires_brief_fields key=value matches the brief
      - at least one requires_parts_any name is in asset.intent.parts
        (empty tuple = "no parts requirement")
      - none of forbids_parts_any is in asset.intent.parts
      - every requires_intent_tags is present in asset.intent.tags
    """

    requires_node_types: tuple[str, ...] = ()
    forbids_node_types: tuple[str, ...] = ()
    requires_brief_fields: Mapping[str, Any] = ()  # type: ignore[assignment]
    requires_parts_any: tuple[str, ...] = ()
    forbids_parts_any: tuple[str, ...] = ()
    requires_intent_tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any] | None) -> "PolicyPrecondition":
        raw = raw or {}
        return cls(
            requires_node_types=tuple(str(x) for x in raw.get("requires_node_types") or ()),
            forbids_node_types=tuple(str(x) for x in raw.get("forbids_node_types") or ()),
            requires_brief_fields=dict(raw.get("requires_brief_fields") or {}),
            requires_parts_any=tuple(str(x) for x in raw.get("requires_parts_any") or ()),
            forbids_parts_any=tuple(str(x) for x in raw.get("forbids_parts_any") or ()),
            requires_intent_tags=tuple(str(x) for x in raw.get("requires_intent_tags") or ()),
        )


@dataclass(frozen=True)
class EdgeTemplate:
    """One edge an expansion creates to an existing node."""

    target_node_type: str
    edge_type: str
    attributes: Mapping[str, Any] = ()  # type: ignore[assignment]

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "EdgeTemplate":
        return cls(
            target_node_type=str(raw["target_node_type"]),
            edge_type=str(raw["edge_type"]),
            attributes=dict(raw.get("attributes") or {}),
        )


@dataclass(frozen=True)
class PolicyExpansion:
    """One structural addition a policy makes when its precondition matches.

    Adds a node by NODE_TYPE (never by family name). Records the
    policy_id that added the node so traces can attribute structure
    correctly.
    """

    add_node_type: str
    count: Any = 1  # int OR {"from_brief_field": str, "default": int}
    placement: Mapping[str, Any] = ()  # type: ignore[assignment]
    attributes_template: Mapping[str, Any] = ()  # type: ignore[assignment]
    edges_to_existing: tuple[EdgeTemplate, ...] = ()

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PolicyExpansion":
        edges_raw = raw.get("edges_to_existing") or ()
        return cls(
            add_node_type=str(raw["add_node_type"]),
            count=raw.get("count", 1),
            placement=dict(raw.get("placement") or {}),
            attributes_template=dict(raw.get("attributes_template") or {}),
            edges_to_existing=tuple(
                EdgeTemplate.from_dict(e) for e in edges_raw if isinstance(e, dict)
            ),
        )


@dataclass(frozen=True)
class CompositionPolicy:
    """Reusable graph-composition rule. Never family-keyed."""

    policy_id: str
    domain: str
    precondition: PolicyPrecondition
    expansions: tuple[PolicyExpansion, ...]
    description: str = ""

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CompositionPolicy":
        return cls(
            policy_id=str(raw["policy_id"]),
            domain=str(raw["domain"]),
            precondition=PolicyPrecondition.from_dict(raw.get("precondition")),
            expansions=tuple(
                PolicyExpansion.from_dict(e)
                for e in (raw.get("expansions") or ())
                if isinstance(e, dict)
            ),
            description=str(raw.get("description") or ""),
        )


def _load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(_load_schema())


def load_policy_pack(path: Path) -> CompositionPolicy:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgePackInvalid(
            f"policy knowledge pack {path} could not be loaded: {exc}"
        ) from exc
    errors = sorted(_validator().iter_errors(raw), key=lambda e: e.path)
    if errors:
        messages = "; ".join(
            f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors
        )
        raise KnowledgePackInvalid(
            f"policy knowledge pack {path} failed schema validation: {messages}"
        )
    return CompositionPolicy.from_dict(raw)


def load_all_policy_packs(
    root: Path | None = None,
) -> Mapping[str, CompositionPolicy]:
    knowledge_root = root or _KNOWLEDGE_ROOT
    if not knowledge_root.exists():
        return {}
    packs: dict[str, CompositionPolicy] = {}
    for entry in sorted(knowledge_root.iterdir()):
        if entry.is_dir():
            continue
        if entry.suffix.lower() != ".json":
            raise KnowledgePackInvalid(
                f"non-JSON file in policy knowledge root: {entry}. "
                f"Knowledge packs must be JSON only."
            )
        pack = load_policy_pack(entry)
        if pack.policy_id in packs:
            raise KnowledgePackInvalid(
                f"duplicate policy_id {pack.policy_id!r} in {entry}"
            )
        packs[pack.policy_id] = pack
    return packs


def precondition_matches(
    precondition: PolicyPrecondition,
    *,
    node_types_present: set[str],
    brief: Mapping[str, Any],
    parts: tuple[str, ...],
    intent_tags: tuple[str, ...],
) -> bool:
    """Return True iff the precondition matches the authored intent.

    Pure function. No side effects.
    """
    for required in precondition.requires_node_types:
        if required not in node_types_present:
            return False
    for forbidden in precondition.forbids_node_types:
        if forbidden in node_types_present:
            return False
    for key, expected in precondition.requires_brief_fields.items():
        if brief.get(key) != expected:
            return False
    if precondition.requires_parts_any:
        if not any(part in parts for part in precondition.requires_parts_any):
            return False
    for forbidden_part in precondition.forbids_parts_any:
        if forbidden_part in parts:
            return False
    for required_tag in precondition.requires_intent_tags:
        if required_tag not in intent_tags:
            return False
    return True
