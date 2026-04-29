"""Wonder-readiness contracts for scene-first Lathe workflows."""

from __future__ import annotations

from .brief import check_brief_scene_consistency, load_and_check_brief_scene, lower_dream_brief_to_scene_graph
from .contracts import (
    CONTRACT_SPECS,
    WonderContractError,
    contract_schema_path,
    get_contract_schema,
    list_contract_summaries,
    load_and_validate_contract,
    validate_contract,
    wonder_capabilities,
    wonder_status,
)
from .decompose import (
    DECOMPOSITION_SCHEMA_VERSION,
    DecomposedBrief,
    DecomposedBriefElement,
    decompose_dream_brief,
)
from .env import WONDER_ENV_PROBE_VERSION, probe_wonder_environment
from .evidence import WONDER_EVIDENCE_TRACE_VERSION, build_evidence_trace, write_evidence_trace
from .examples import (
    PREVIEW_EVIDENCE_VERSION,
    SCENE_SOURCE_STATUS_VERSION,
    WONDER_EXAMPLE_CATALOG_VERSION,
    WONDER_EXAMPLE_REPORT_VERSION,
    catalog_wonder_examples,
    render_example_catalog_markdown,
    validate_wonder_example,
    write_example_golden_files,
)
from .llm import (
    LLM_DIAGNOSTIC_SUMMARY_VERSION,
    LLM_REPAIR_PLAYBOOK_VERSION,
    build_repair_playbook,
    compact_diagnostic,
    compact_diagnostic_summary,
    diagnose_for_llm,
    diagnostic_repair_options,
    generate_scene_plan,
    semantic_patch_request_to_scene_patch,
    validate_repair_playbook_payload,
)
from .readiness import WONDER_ALPHA_GATE_REPORT_VERSION, build_alpha_gate_report
from .reports import (
    WONDER_BENCHMARK_REPORT_VERSION,
    WONDER_CLI_CATALOG_VERSION,
    WONDER_CONTRACT_CATALOG_VERSION,
    WONDER_PERFORMANCE_REPORT_VERSION,
    WONDER_SECURITY_REPORT_VERSION,
    render_final_readiness_markdown,
    write_readiness_report_files,
)

__all__ = [
    "CONTRACT_SPECS",
    "DECOMPOSITION_SCHEMA_VERSION",
    "LLM_DIAGNOSTIC_SUMMARY_VERSION",
    "LLM_REPAIR_PLAYBOOK_VERSION",
    "PREVIEW_EVIDENCE_VERSION",
    "SCENE_SOURCE_STATUS_VERSION",
    "WONDER_ALPHA_GATE_REPORT_VERSION",
    "WONDER_BENCHMARK_REPORT_VERSION",
    "WONDER_CLI_CATALOG_VERSION",
    "WONDER_CONTRACT_CATALOG_VERSION",
    "WONDER_ENV_PROBE_VERSION",
    "WONDER_EVIDENCE_TRACE_VERSION",
    "WONDER_EXAMPLE_CATALOG_VERSION",
    "WONDER_EXAMPLE_REPORT_VERSION",
    "WONDER_PERFORMANCE_REPORT_VERSION",
    "WONDER_SECURITY_REPORT_VERSION",
    "DecomposedBrief",
    "DecomposedBriefElement",
    "WonderContractError",
    "build_alpha_gate_report",
    "build_evidence_trace",
    "build_repair_playbook",
    "catalog_wonder_examples",
    "check_brief_scene_consistency",
    "compact_diagnostic",
    "compact_diagnostic_summary",
    "contract_schema_path",
    "decompose_dream_brief",
    "diagnose_for_llm",
    "diagnostic_repair_options",
    "generate_scene_plan",
    "get_contract_schema",
    "list_contract_summaries",
    "load_and_check_brief_scene",
    "load_and_validate_contract",
    "lower_dream_brief_to_scene_graph",
    "probe_wonder_environment",
    "render_example_catalog_markdown",
    "render_final_readiness_markdown",
    "semantic_patch_request_to_scene_patch",
    "validate_contract",
    "validate_repair_playbook_payload",
    "validate_wonder_example",
    "wonder_capabilities",
    "wonder_status",
    "write_evidence_trace",
    "write_example_golden_files",
    "write_readiness_report_files",
]
