# Stage Contracts

Lathe's build stages have one public artifact each, plus trace fields consumed
by package traces, selector manifests, and release review. The machine-readable
source of truth is `lathe.stage_contracts.STAGE_CONTRACTS`; this page mirrors
that inventory for maintainers.

| Stage | Public artifact | Required input surface | Output schema highlights | Trace records | Failure modes |
| --- | --- | --- | --- | --- | --- |
| `shape` | `stages/shape/bundle.json` | materialized intent, selected shape backend, provider config, reference conditioning | `backend_id`, `backend_version`, `selected_candidate_id`, `candidates[]`, `provider_report`, `provenance` | `stage_bundle_refs.shape`, `shape`, `candidate_selection` | unsupported handoff contract, provider failure, no selected candidate, geometry-strict watertightness failure |
| `topology` | `stages/topology/bundle.json` | shape bundle, topology backend, `build.topology` | `backend_id`, `backend_version`, `mesh_uri`, `mesh_stats`, `adapter_report` | `stage_bundle_refs.topology`, `topology` | unsupported consumed shape contract, Blender adapter failure, backend unavailable |
| `uv` | `stages/uv/bundle.json` | topology bundle, UV backend, `build.uv` | `backend_id`, `backend_version`, `mesh_uri`, `uv_sets`, `adapter_report` | `stage_bundle_refs.uv`, `uv` | unsupported consumed topology contract, UV backend unavailable, mesh export failure |
| `surface` | `stages/surface/bundle.json` | UV bundle, surface programs, material graph, runtime surface config | `backend_id`, `materials`, `surface_control_pack`, `surface_backend_report` | `stage_bundle_refs.surface`, `surface` | surface backend failure, texture request/output validation failure |
| `execution` | `stages/execution/bundle.json` | optimize bundle, execution policy, runtime execution config | `backend_id`, `diagnostics`, `render_eval_ir`, `blend_artifact_ir` | `stage_bundle_refs.execution`, `execution` | sandboxed subprocess failure, expected artifact missing, stderr deny pattern |
| `rig` | `stages/rig/bundle.json` | surface bundle, topology runtime mesh, `build.rig` | `backend_id`, `type`, `joints` | `stage_bundle_refs.rig` | missing topology runtime mesh, unsupported rig config |
| `interfaces` | `stages/interfaces/bundle.json` | rig bundle, topology runtime mesh, `build.interfaces` | `backend_id`, `sockets`, `pivots`, `anchors`, `aabbs` | `stage_bundle_refs.interfaces` | invalid typed interface entry, duplicate interface id |
| `physics` | `stages/physics/bundle.json` | interfaces bundle, topology runtime mesh, `build.physics` | `backend_id`, `collision`, `mass_kg`, `collision_uri` | `stage_bundle_refs.physics` | collision proxy export failure, missing topology runtime mesh |
| `optimize` | `stages/optimize/bundle.json` | physics bundle, UV runtime mesh, `build.optimize` | `backend_id`, `lods`, `collision`, `budget_report`, `diagnostics` | `stage_bundle_refs.optimize` | empty runtime mesh, LOD export failure, budget gate diagnostic |
| `validate` | `stages/validate/report.json` | optimize bundle, validator runtime, validate rules, critic score config | `certified`, `threshold`, `score`, `diagnostics`, `failure_summary` | `stage_bundle_refs.validate`, `diagnostics`, `repairs_applied` | validator diagnostic, ensure rule failure, score below threshold |
| `package` | `stages/package/bundle.json` | optimize bundle, validate report, package formats, engine manifest context | `backend_id`, `outputs`, `manifest_path`, `trace_path`, `selector_manifest_path` | `stage_bundle_refs.package`, `package_outputs`, `previews` | package artifact collision, format export failure, selector manifest validation error |

Any stage addition or artifact shape change must update this page, the
`STAGE_CONTRACTS` inventory, and the corresponding tests before release.
