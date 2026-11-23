# T-1472 -- declared core-unit family: one process vs shards

- subject fingerprint (before): `6bd02562455126e0`; record fingerprint (after): `6bd02562455126e0`
- before: one process, whole discovery -- run 2037.7 s (wall incl. copy 2055.5 s), ran 3580, discovered 3580, red 38
- after: 6 shards -- wall 763.3 s incl. copies, ran 3580, discovered 3580, red 30, verdict PASS new_red 0
- shards: #0 20 tests 688.9 s PASS; #1 792 tests 576.7 s FAIL; #2 753 tests 665.2 s FAIL; #3 550 tests 590.4 s FAIL; #4 852 tests 630.6 s FAIL; #5 613 tests 607.6 s PASS

## Red set

- only in before: ['test_opencode_adapter.OpenCodeAdapterIntegration.test_p0_7_actor_resolution_uses_canonical_or_explicit_ownership', 'test_opencode_bound_launch_smoke.BoundOpenCodeNativeSmoke.test_optional_explicit_launch_is_checked_and_does_not_leak', 'test_opencode_host_smoke.OpenCodeHostSmoke.test_3_the_installed_artifact_carries_the_whole_chain', 'test_session_binding.SeatGateTests.test_a_foreign_bound_claim_is_not_taken_over_by_start', 'test_session_binding.SeatGateTests.test_the_refused_start_leaves_the_owner_exactly_where_it_was', 'test_source_quarantine_route.QuarantineRouteTests.test_other_source_refusals_are_preserved_without_guessing_quarantine', 'test_t1363_zero_manual_entry.HumanRefusalTests.test_a_foreign_owner_refusal_says_who_owns_the_seat', 'test_t1363_zero_manual_entry.StartEntryTests.test_start_never_steals_a_live_foreign_seat']
- only in after: []

## Per module (seconds; before = one process, after = inside its shard)

| module | before | after |
|---|---:|---:|
| test_conformance_lineage | 372.4 | 686.2 |
| test_opencode_host_smoke | 67.8 | 100.9 |
| test_t1363_zero_manual_entry | 67.7 | 127.6 |
| test_t1412_conformance_truth | 61.1 | 66.5 |
| test_entry_point_parity | 60.8 | 91.0 |
| test_recovery_reachability | 55.3 | 90.3 |
| test_t1461_source_append | 53.3 | 111.3 |
| test_command_routing | 53.0 | 60.6 |
| test_t1326_board_compaction | 51.9 | 144.5 |
| test_opencode_adapter | 48.2 | 83.0 |
| test_t1411_stale_complete_resolution | 44.7 | 91.6 |
| test_opencode_bound_launch_smoke | 42.9 | 95.4 |
| test_refusal_routes | 42.8 | 72.5 |
| test_settled_projection | 37.6 | 91.2 |
| test_ticket_supersession | 33.6 | 64.5 |
| test_adapter_parity | 30.9 | 41.1 |
| test_ticket_retirement | 28.2 | 73.9 |
| test_continue_chain | 26.8 | 50.4 |
| test_producer_terminal_consistency | 23.7 | 43.7 |
| test_router_closure_readiness | 23.7 | 50.5 |
| test_t1327_zero_manual_recovery | 23.6 | 37.4 |
| test_work_reverify_cli | 23.3 | 24.3 |
| test_crew_applicability | 23.2 | 63.9 |
| test_conformance_repair_boundary | 23.0 | 33.2 |
| test_source_receipts | 22.7 | 81.4 |
| test_validator_layout_parity | 22.1 | 25.4 |
| test_control_primitives | 20.5 | 42.9 |
| test_guard_hostile_matrix | 20.2 | 34.0 |
| test_improve_reconcile | 20.1 | 45.4 |
| test_request_clause_closure | 20.0 | 37.0 |
| test_t1476_retired_source_livelock | 18.6 | 27.8 |
| test_guard_execution_reachability | 17.8 | 28.3 |
| test_debt_gate | 17.7 | 32.9 |
| test_boot_locator | 17.1 | 19.8 |
| test_t1446_supervise | 15.9 | 19.3 |
| test_audit_2026_08_28_all3 | 15.6 | 28.7 |
| test_src085_conformance_disposition | 14.8 | 19.0 |
| test_t1389_foreign_delta_adoption | 13.2 | 18.2 |
| test_saipen_metrics | 13.2 | 20.2 |
| test_canonical_write_route | 13.1 | 17.6 |
| test_runtime_bootstrap | 13.0 | 23.1 |
| test_public_closure_cli | 12.6 | 21.1 |
| test_t1304_r004_dry_run_purity | 12.0 | 15.3 |
| test_operator_task_witness | 11.5 | 24.8 |
| test_metadata_repair | 11.5 | 22.8 |
| test_metrics_acceptance | 11.1 | 18.6 |
| test_intent_audit_fixes | 11.0 | 22.9 |
| test_entry_answer_agrees | 10.9 | 19.4 |
| test_check_inventory | 9.8 | 13.8 |
| test_t1446_auto_recall | 9.3 | 16.7 |
| test_dependency_resume_liveness | 8.4 | 19.9 |
| test_session_binding | 8.4 | 15.4 |
| test_closure_provenance | 8.2 | 23.9 |
| test_orchestration_repair | 7.6 | 23.1 |
| test_external_resolution | 7.4 | 13.8 |
| test_audit_manifest | 7.0 | 9.0 |
| test_host_bootstrap | 6.8 | 14.2 |
| test_unknown_tool_fail_closed | 6.7 | 7.5 |
| test_t1429_deferred_due | 6.7 | 13.8 |
| test_pending_ingress | 6.6 | 12.9 |
| test_actor_binding_lifecycle | 6.6 | 7.2 |
| test_t1473_handback | 5.9 | 12.3 |
| test_source_retirement | 5.8 | 11.3 |
| test_userperson_global | 5.8 | 8.5 |
| test_field_fixture_isolation | 5.7 | 14.5 |
| test_core_unit_gate | 5.7 | 20.4 |
| test_user_wait_release | 5.6 | 11.8 |
| test_native_host_guard | 5.5 | 7.4 |
| test_t1474_start_goal_entry | 5.5 | 9.6 |
| test_t1304_r004_transition | 5.4 | 9.9 |
| test_hostile_wave_regressions | 5.4 | 8.9 |
| test_remediation_self_consistency | 5.1 | 8.1 |
| test_adaptive_runtime | 5.0 | 6.0 |
| test_t1407_structural_log_compaction | 5.0 | 12.0 |
| test_runtime_generation_identity | 5.0 | 8.3 |
| test_t1316_recovery_already_applied | 4.9 | 16.0 |
| test_log_normalize | 4.7 | 9.2 |
| test_capability_boundary | 4.7 | 4.7 |
| test_v7_producer_parallelism | 4.7 | 7.6 |
| test_improve_gate | 4.6 | 7.9 |
| test_core_ownership_routing | 4.5 | 15.3 |
| test_source_quarantine_route | 4.4 | 9.3 |
| test_audit_inbox | 4.4 | 10.7 |
| test_handoff_archive_cross_repo | 4.1 | 8.0 |
| test_authority_capture | 4.0 | 11.0 |
| test_foreign_observation_authority | 3.9 | 6.8 |
| test_explicit_claim | 3.6 | 14.4 |
| test_concurrency_independence | 3.5 | 5.5 |
| test_project_root_session_binding | 3.5 | 6.4 |
| test_next_action_deadlock | 3.5 | 7.2 |
| test_t1446_duplicate_ingress | 3.4 | 5.8 |
| test_reconcile_valve | 3.4 | 7.4 |
| test_t1457_ingress_obligation | 3.3 | 5.1 |
| test_runtime_namespace | 3.2 | 4.4 |
| test_audit_2026_08_27_core | 3.2 | 4.7 |
| test_journal_nested_targets | 3.1 | 8.8 |
| test_effect_authorization | 3.0 | 6.5 |
| test_t1398_ingress_shell_operator | 2.9 | 5.9 |
| test_refusal_registry | 2.8 | 3.4 |
| test_cold_recovery | 2.7 | 3.6 |
| test_search_transport | 2.7 | 4.3 |
| test_automation_block | 2.7 | 5.2 |
| test_worker_turnover | 2.6 | 3.0 |
| test_regression_gate | 2.6 | 12.0 |
| test_module_duplication_guard | 2.4 | 4.4 |
| test_t1383_ticket_add_route | 2.4 | 4.2 |
| test_install_drift | 2.4 | 4.3 |
| test_validator_findings | 2.3 | 3.6 |
| test_t1304_review_p0_repair | 2.3 | 8.0 |
| test_foreign_owner_terminal_route | 2.2 | 4.5 |
| test_inject_digest | 2.2 | 4.7 |
| test_t1453_ingress_clause | 2.1 | 4.3 |
| test_engine_module_identity | 2.0 | 3.7 |
| test_crew_liveness_drift | 1.8 | 2.8 |
| test_audit_dogfood | 1.8 | 3.8 |
| test_t1386_canonical_payload | 1.7 | 3.1 |
| test_distribution_report | 1.7 | 2.3 |
| test_audit_enqueue | 1.5 | 2.9 |
| test_audit_2026_08_29_all3_impl | 1.4 | 3.3 |
| test_source_refusal_routing | 1.4 | 6.3 |
| test_audit_ingest_resume | 1.3 | 2.8 |
| test_xpatch | 1.3 | 2.6 |
| test_src085_improve_run_body | 1.3 | 2.4 |
| test_source_multiwork | 1.2 | 4.7 |
| test_t1454_distribution_blocker | 1.1 | 2.2 |
| test_evidence_hygiene | 1.1 | 2.7 |
| test_continue_improve_fallthrough | 1.1 | 2.1 |
| test_audit_2026_08_30_all3_impl | 1.1 | 1.5 |
| test_recovered_attribution | 1.0 | 1.5 |
| test_supervisor | 0.9 | 1.4 |
| test_canonical_command_reachability | 0.9 | 1.0 |
| test_continue_entry | 0.8 | 1.1 |
| test_t1458_queue_reservation | 0.8 | 2.3 |
| test_recovery_noop_targets | 0.8 | 2.0 |
| test_opencode_launch_binding | 0.8 | 1.0 |
| test_t1472_core_unit_shards | 0.8 | 0.7 |
| test_generation_migration | 0.8 | 1.7 |
| test_gpu_lane | 0.7 | 1.2 |
| test_knowledge | 0.7 | 1.4 |
| test_reverify | 0.7 | 2.6 |
| test_verify_oracle | 0.6 | 0.4 |
| test_cold_agent_truth | 0.6 | 0.5 |
| test_t1460_consumed_ingress | 0.6 | 1.6 |
| test_scenario_runner_isolation | 0.5 | 1.8 |
| test_legacy_lifecycle_compat | 0.4 | 1.4 |
| test_audit_2026_08_27_w2 | 0.4 | 0.6 |
| test_acceptance | 0.3 | 0.4 |
| test_t1479_core_unit_consistent_copy | 0.3 | 0.3 |
| test_guard_root_parity | 0.2 | 0.4 |
| test_audit_transport_loop | 0.2 | 0.8 |
| test_reconcile_legacy_output_field | 0.2 | 0.9 |
| test_recover_approved_repair | 0.2 | 0.6 |
| test_instruction_loader_contracts | 0.2 | 0.4 |
| test_defect_delta_controls | 0.1 | 0.8 |
| test_guard_admission | 0.1 | 0.3 |
| test_autonomy_audit_fixes | 0.1 | 0.2 |
| test_audit_enqueue_boundary | 0.1 | 0.4 |
| test_audit_provenance | 0.1 | 0.2 |
| test_instruction_home_parity | 0.1 | 0.2 |
| test_xpatch_controls | 0.1 | 0.4 |
| test_protocol_registry | 0.1 | 0.2 |
| test_adoption_section_parity | 0.1 | 0.2 |
| test_t1434_cross_shape_index | 0.1 | 0.1 |
| test_t1452_manifest_authority | 0.1 | 0.1 |
| test_log_detail_evidence | 0.1 | 0.2 |
| test_guard_events | 0.1 | 0.1 |
| test_hermetic_env | 0.1 | 0.1 |
| test_watchdog | 0.1 | 0.1 |
| test_self_resolving_gates | 0.1 | 0.1 |
| test_guard_surface_parity | 0.1 | 0.1 |
| test_narrative_authority | 0.0 | 0.1 |
| test_audit_envelope | 0.0 | 0.1 |
| test_saitranslate_charter_namespace | 0.0 | 0.0 |
| test_event_taxonomy_owner | 0.0 | 0.0 |
| test_reconcile_history_ledger_blocked | 0.0 | 0.0 |
| test_core_audit_containment | 0.0 | 0.0 |
| test_hush_runtime | 0.0 | 0.0 |
| test_sandbox_work_surface | 0.0 | 0.1 |
| test_state_scalar_quoting | 0.0 | 0.0 |
| test_conformance_projection | 0.0 | 0.0 |
| test_host_launch_net | 0.0 | 0.0 |
| test_conformance_corpus | 0.0 | 0.0 |
| test_response_surface_contract | 0.0 | 0.0 |
| test_t1484_soak_report_survives | 0.0 | 0.0 |
| test_audit_scope | 0.0 | 0.0 |
| test_vocabulary_parity | 0.0 | 0.0 |
| test_ccc_ff_control | 0.0 | 0.0 |
| test_verification_grammar | 0.0 | 0.0 |
| test_repeated_cc | 0.0 | 0.0 |
| test_board_pseudo_link | 0.0 | 0.0 |
| test_opencode_live_evaluator | 0.0 | 0.0 |
| test_verify_scope_isolation | 0.0 | 0.0 |
| test_ledger_gap | 0.0 | 0.0 |
| test_log_stamp_guard | 0.0 | 0.0 |
| test_t1445_failure_field_scope | 0.0 | 0.0 |
| test_warn_ownership_probe | 0.0 | 0.0 |
| test_audit_route | 0.0 | 0.0 |
| test_log_ticket_slot | 0.0 | 0.0 |
| test_opencode_live_session | 0.0 | 0.0 |
| test_t1327_live_acceptance | 0.0 | 0.0 |

## Attribution of the red-set difference

Same subject (fingerprint 6bd02562455126e0) in both runs. No id is red in the
sharded run and green in the one-process run. Every id red only in the
one-process run is a baseline id (tools/core_unit_baseline.json), so the SHIP
verdict (new red outside the baseline) cannot differ between the two modes.

- test_session_binding x2, test_t1363_zero_manual_entry x2: fixture claim
  stamps come from `test_t1363_zero_manual_entry._NOW`, read at import
  (discovery). A module reached more than the 15-minute claim liveness window
  after discovery sees its "live" claim as stale. Measured at HEAD 3580b648:
  the 5 ids green in a fresh process; with `_NOW` aged 30 minutes 4 of them go
  red (scratch probe t1472_aged5.py). Owner: T-1478 (fix staged in batch 2).
- test_source_quarantine_route ...test_other_source_refusals_are_preserved_without_guessing_quarantine:
  order-dependent. test_metrics_acceptance.ObservationalTests.test_an_unreadable_engine_degrades_rather_than_raising
  deletes every saipen_engine.* module and never restores them, so the later
  module's patch.object hits a stale module object. Measured at HEAD: OK alone,
  3 subtest FAIL right after the purge test in one process. Owner: T-1490.
- test_opencode_adapter p0_7, test_opencode_bound_launch_smoke, test_opencode_host_smoke test_3:
  these modules build their fixtures from the same import-time clocks
  (test_t1363_zero_manual_entry / test_guard_hostile_matrix.CLAIM_NOW). Green in
  the one-process HEAD run of 1600 s (record 8498b4e5e7f00317), red in this
  one-process run of 2038 s: run-length dependent. Inferred, not directly
  reproduced: the aged-clock probe for these three hung outside the family
  harness (a real opencode child) and was stopped. Owner: T-1478.

Ids the Work fixed (one-process HEAD 3580b648 vs one-process batch-1 tree):
test_canonical_command_reachability x2 (T-1486). Nothing else changed colour
between the two one-process runs except the three run-length-dependent ids
above.
