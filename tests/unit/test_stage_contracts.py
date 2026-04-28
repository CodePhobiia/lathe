from __future__ import annotations

from lathe.executor import STAGE_ORDER
from lathe.stage_contracts import STAGE_CONTRACTS, STAGE_ORDER_CONTRACT, stage_contract


def test_stage_contract_inventory_matches_executor_stage_order() -> None:
    assert tuple(STAGE_ORDER) == STAGE_ORDER_CONTRACT
    assert tuple(STAGE_CONTRACTS) == STAGE_ORDER_CONTRACT


def test_every_stage_contract_has_schema_trace_and_failure_modes() -> None:
    for stage in STAGE_ORDER_CONTRACT:
        contract = stage_contract(stage)
        assert contract.stage == stage
        assert contract.inputs
        assert contract.output_schema
        assert contract.artifact.startswith(f"stages/{stage}/")
        assert contract.trace_records
        assert contract.failure_modes


def test_validate_contract_exposes_actionable_failure_summary() -> None:
    contract = stage_contract("validate")

    assert "failure_summary" in contract.output_schema
    assert "score below threshold" in contract.failure_modes
