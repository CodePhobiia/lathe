from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProposalDelta:
    delta_id: str
    kind: str
    target_region: str
    source: str
    accepted: bool
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ShapeProposal:
    proposal_id: str
    source_id: str
    candidate_index: int
    score: float
    deltas: list[ProposalDelta] = field(default_factory=list)
    assessment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["deltas"] = [delta.to_dict() for delta in self.deltas]
        return payload


@dataclass
class ProposalBank:
    attempted_sources: list[str]
    proposals: list[ShapeProposal]

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempted_sources": list(self.attempted_sources),
            "proposals": [proposal.to_dict() for proposal in self.proposals],
        }
