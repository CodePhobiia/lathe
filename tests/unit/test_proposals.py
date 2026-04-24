"""Unit tests for ``lathe.proposals``.

Covers the small dataclass surface used by the shape provider mux to
record provider proposals and accept/reject decisions:

* ``ProposalDelta`` and ``ShapeProposal`` construction + serialization
* score-based sort order over a list of proposals
* empty bank handling
* malformed construction (missing required fields) raises
* the accepted-vs-rejected distinction is preserved end-to-end
"""

from __future__ import annotations

import unittest

from lathe.proposals import ProposalBank, ProposalDelta, ShapeProposal


def _delta(delta_id: str = "d1", *, accepted: bool = True, kind: str = "panel_extrude") -> ProposalDelta:
    return ProposalDelta(
        delta_id=delta_id,
        kind=kind,
        target_region="body",
        source="prov.x",
        accepted=accepted,
        reason="ok" if accepted else "rejected_by_critic",
        metrics={"score": 0.9 if accepted else 0.2},
    )


def _proposal(pid: str, *, score: float, deltas: list[ProposalDelta] | None = None) -> ShapeProposal:
    return ShapeProposal(
        proposal_id=pid,
        source_id="prov.x",
        candidate_index=0,
        score=score,
        deltas=list(deltas or []),
        assessment={"score": score},
    )


class ProposalConstructionTests(unittest.TestCase):
    def test_proposal_round_trips_through_to_dict(self) -> None:
        proposal = _proposal("p1", score=0.5, deltas=[_delta("d1")])
        payload = proposal.to_dict()
        self.assertEqual(payload["proposal_id"], "p1")
        self.assertEqual(payload["score"], 0.5)
        self.assertEqual(len(payload["deltas"]), 1)
        self.assertEqual(payload["deltas"][0]["delta_id"], "d1")
        self.assertTrue(payload["deltas"][0]["accepted"])

    def test_proposal_score_drives_sort_order(self) -> None:
        bank = [
            _proposal("low", score=0.1),
            _proposal("high", score=0.9),
            _proposal("mid", score=0.5),
        ]
        ranked = sorted(bank, key=lambda p: p.score, reverse=True)
        self.assertEqual([p.proposal_id for p in ranked], ["high", "mid", "low"])

    def test_empty_proposal_bank_serializes(self) -> None:
        bank = ProposalBank(attempted_sources=["prov.x"], proposals=[])
        payload = bank.to_dict()
        self.assertEqual(payload, {"attempted_sources": ["prov.x"], "proposals": []})

    def test_malformed_delta_missing_required_field_raises(self) -> None:
        with self.assertRaises(TypeError):
            ProposalDelta(  # type: ignore[call-arg]
                delta_id="d1",
                kind="panel_extrude",
                target_region="body",
                # missing source/accepted/reason
            )

    def test_accepted_vs_rejected_distinction_preserved(self) -> None:
        proposal = _proposal(
            "p1",
            score=0.4,
            deltas=[_delta("a", accepted=True), _delta("b", accepted=False)],
        )
        payload = proposal.to_dict()
        accepted = [d for d in payload["deltas"] if d["accepted"]]
        rejected = [d for d in payload["deltas"] if not d["accepted"]]
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(accepted[0]["delta_id"], "a")
        self.assertEqual(rejected[0]["delta_id"], "b")
        # rejected delta carries its own reason
        self.assertNotEqual(accepted[0]["reason"], rejected[0]["reason"])

    def test_proposal_bank_records_attempted_sources(self) -> None:
        bank = ProposalBank(
            attempted_sources=["prov.a", "prov.b"],
            proposals=[_proposal("p1", score=0.5)],
        )
        payload = bank.to_dict()
        self.assertEqual(payload["attempted_sources"], ["prov.a", "prov.b"])
        self.assertEqual(len(payload["proposals"]), 1)
        # to_dict makes a copy of attempted_sources
        bank.attempted_sources.append("prov.c")
        self.assertEqual(payload["attempted_sources"], ["prov.a", "prov.b"])


if __name__ == "__main__":
    unittest.main()
