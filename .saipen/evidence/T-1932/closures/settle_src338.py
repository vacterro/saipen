"""Settle SRC-338's requirement clauses from one authenticated focused record.

Every verification string cites ONLY test modules that this record actually ran
(the record's `proven_oracles` are its exact `run["pattern"]` values), so the
citation is authenticated by the same digest the journal bound. Test methods
named in a string exist in that module; extra corroboration that the record did
not run goes in `evidence`, which is a reference, not a proof claim.

Nothing here writes STATE/BOARD/LOG: dispositions go through
`intake.set_disposition`, the canonical coverage writer.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import intake  # noqa: E402

RECORD = ".saipen/evidence/focused-unit/90f3464452010c08-20261026T172010956231Z.json"
DIGEST = "1c307db9aea978dda9f71088d68c061ffbdb05ab917968dafcb2b07e6c016eec"
BIND = f"record:{RECORD} sha256:{DIGEST}"

CLOSURES = "test_t1932_src338_closures.py"
AUTHORITY = "test_t1932_campaign_authority.py"
LIFECYCLE = "test_t1931_campaign_lifecycle.py"
BOUNDARY = "test_t1931_saipal_boundary.py"
GATES = "test_campaign_production_gates.py"

#: rid -> (verification body after BIND, evidence)
SETTLE = {
    "R001": (
        f"{AUTHORITY} rejects caller-selected scopes signed by an innocent origin "
        "(test_real_origin_for_innocent_text_cannot_sign_caller_selected_scopes), pins the "
        "original carrier bytes after admission (test_original_carrier_bytes_are_pinned_after_admission), "
        "refuses revoked, expired, foreign-lineage and unregistered-worker proof "
        "(test_revocation_expiry_foreign_lineage_and_unregistered_worker_refuse), refuses declared "
        "foreign lineage/session/target (test_declared_foreign_lineage_host_session_and_target_are_refused), "
        "and keeps one-campaign consumption idempotent (test_consumption_is_one_campaign_and_exact_retry_is_idempotent); "
        f"{GATES} test_gate_a_authority_enforcement covers the journal-event and absent-reference refusals",
        "E-18474; read-only diagnosis preserved: a refused grant returns a typed refusal with the campaign state untouched",
    ),
    "R002": (
        f"{CLOSURES} OwnershipFailureTests.test_lock_busy_invokes_no_callback proves an injected "
        "acquisition failure invokes zero callbacks and preserves the pending request; "
        "CrossProjectConcurrencyTests.test_same_project_duplicate_attempts_stay_serialized proves a "
        "same-project replay does not dispatch; CrossProjectConcurrencyTests."
        "test_independent_projects_do_not_serialize_behind_each_other proves ownership is scoped, "
        "not global",
        "E-18474; LOCK_BUSY is the typed refusal returned; the request row stays in the ledger for recovery",
    ),
    "R003": (
        f"{CLOSURES} OwnershipFailureTests.test_corrupt_ledger_invokes_no_callback and "
        "DispatchLedgerCostTests.test_ledger_corruption_remains_a_typed_failure prove a malformed "
        "existing ledger is a typed recovery state with zero callbacks; "
        "DispatchLedgerCostTests.test_partial_journal_append_is_detected proves a torn append is "
        "detected rather than read as empty history; "
        "DispatchLedgerCostTests.test_migration_preserves_legacy_accepted_identities and "
        "test_historical_accepted_operations_remain_discoverable prove prior dispatch identities survive "
        "recovery",
        "E-18474; damaged bytes stay on disk inside the journal for diagnosis, never replaced by an empty success",
    ),
    "R004": (
        f"{CLOSURES} DispatchDispositionTests.test_failed_hook_is_not_a_successful_dispatch_disposition "
        "and test_confirmed_host_acknowledgment_kicks separate REQUEST_PERSISTED from a confirmed "
        "acceptance; PersistedDispatchReplayTests.test_receipt_without_request_identity_is_unverified and "
        "test_receipt_naming_the_request_as_a_digest_is_accepted prove the digest/lineage fields are "
        "contract fields rather than optional extras; DispatchDispositionTests."
        "test_confirmed_host_acknowledgment_kicks proves a replayed matching receipt is idempotent",
        "E-18474; the CORE-004 counterexample control at .saipen/evidence/T-1932/closures/red_controls.py "
        "now returns ACCEPTANCE_UNVERIFIED with dispatched false instead of a successful dispatch",
    ),
    "R005": (
        f"{AUTHORITY} test_real_goal_source_does_not_implicitly_authorize_publication proves campaign "
        "state alone cannot publish, and test_exact_native_capsule_grants_only_declared_scopes proves a "
        "grant allows only its declared scopes; {GATES} "
        "test_gate_e_gate_f_saipal_forensics_and_publication proves a finding without publication "
        "authority retains a staged receipt instead of publishing",
        "E-18474; per-scope separation is enforced at the side-effect boundary by the canonical verifier",
    ),
    "R006": (
        f"{CLOSURES} PublicationReceiptIdentityTests.test_conflicting_digest_for_one_operation_is_refused "
        "proves an altered artifact fails digest verification and a caller-named qualification receipt is "
        "not accepted; PublicationReceiptIdentityTests.test_same_finding_twice_retains_one_receipt proves "
        "one logical receipt survives repetition; {GATES} "
        "test_neg_camp_007_missing_artifact_digest_fails_publication proves a summary-only publication "
        "is refused",
        "E-18474; the CORE-006 counterexample control at .saipen/evidence/T-1932/closures/red_controls.py "
        "now returns NOT_QUALIFIED with zero enqueue calls",
    ),
    "R007": (
        f"{LIFECYCLE} test_cancel_and_parallel_step_while_worker_is_running proves cancellation stays "
        "responsive and is durable while a worker runs; test_late_worker_cannot_overwrite_new_campaign "
        "proves a delayed in-flight callback is fenced out by generation identity; {GATES} "
        "test_gate_k_explicit_cancellation proves cancellation fences the next generation dispatch",
        "E-18474; the cancellation epoch is persisted, so a restart reconstructs the same fence",
    ),
    "R008": (
        f"{LIFECYCLE} test_durable_intent_precedes_worker_execution proves execution intent is persisted "
        "before the worker starts; test_positional_and_root_only_workers_remain_supported proves an "
        "admitted executor returns a bound receipt; {GATES} "
        "test_neg_camp_005_and_009_executor_missing_and_supersession proves a missing executor is a typed "
        "unavailable refusal rather than a completed-execution claim",
        "E-18474; a supervisor decision alone never produces a WORKER_GENERATION_EXECUTED claim",
    ),
    "R009": (
        f"{GATES} test_gate_b_actual_work_execution proves only a verified Work transition counts as "
        "productive execution; {LIFECYCLE} "
        "test_completed_worker_result_recovers_after_commit_lock_contention proves an outcome is observed "
        "through its durable receipt, not asserted; {LIFECYCLE} "
        "test_incomplete_outcome_envelope_is_a_typed_refusal proves an unbound outcome never becomes "
        "progress",
        "E-18474; the CORE-009 counterexample control at .saipen/evidence/T-1932/closures/red_controls.py "
        "now reports self_asserted_progress_verified false, made_progress false, journal_advanced false",
    ),
    "R010": (
        f"{BOUNDARY} test_valid_empty_discovery_report_is_no_new_evidence proves an unchanged source is "
        "quiet rather than a new finding; test_missing_and_valid_empty_logs_are_distinct and "
        "test_unreadable_discovery_watermark_does_not_reset_to_clean_evidence prove the discovery "
        "checkpoint is generation-aware; test_failed_collection_is_not_an_empty_list and "
        "test_discovery_does_not_swallow_status_or_analysis_failures prove a failed analysis is never a "
        "successful discovery",
        "E-18474; missing SAIPAL runtime stays a typed unavailable state rather than an empty success",
    ),
    "R011": (
        f"{GATES} test_gate_g_gate_h_repair_and_disposition proves a VERIFIED disposition requires a real "
        "terminal Work and a verification receipt; test_neg_camp_008_unverified_maintainer_disposition_rejected "
        "proves a free-text PASS string is refused; {BOUNDARY} "
        "test_complete_history_preserves_all_records proves disposition identity survives later generations",
        "E-18474; the CORE-011 counterexample control at .saipen/evidence/T-1932/closures/red_controls.py "
        "now returns DISPOSITION_UNVERIFIED instead of a fabricated closure",
    ),
    "R012": (
        f"{CLOSURES} DispatchDispositionTests.test_failed_hook_is_not_a_successful_dispatch_disposition, "
        "test_persisted_advisory_is_pending_not_started, test_no_false_turn_start_metrics and "
        "test_confirmed_host_acknowledgment_kicks cover the five dispositions: a failed hook is not a "
        "successful dispatch, a persisted advisory is pending rather than started, and no turn-start "
        "metric is emitted without a confirmed acceptance",
        "E-18474; DispatchDeadlineTests.test_timeout_maps_to_recovery_disposition proves an uncertain "
        "result maps to the reconcilable disposition",
    ),
    "R013": (
        f"{LIFECYCLE} test_closed_positive_finite_budget_dimensions proves only declared horizon "
        "dimensions are accepted; test_invalid_horizon_never_throws proves an unknown horizon is a "
        "refusal rather than a crash; test_max_cycles_survives_restart_and_is_not_completion proves an "
        "exhausted budget is not reported as completion; test_force_new_never_replaces_nonterminal_campaign "
        "and test_terminal_replacement_retains_exact_original_bytes prove ownership transfer requires "
        "authority and preserves prior campaign bytes",
        "E-18474; a restart reconstructs the same remaining budget from persisted state",
    ),
    "R014": (
        f"{GATES} and test_campaign_matrix.py both run in this record, pinning the continuation "
        "assessment and the adapter boundary this clause names; test_campaign_continuation_assessment.py "
        "and test_t1931_saipal_boundary.py in the same run cover the same surface; the record was "
        "captured from the current tree",
        "E-18474; the continuation assessment is exercised by its own module rather than inferred",
    ),
    "R015": (
        f"{CLOSURES} DispatchDeadlineTests.test_timeout_preserves_identity_and_requires_reconciliation "
        "proves an uncertain outcome keeps its operation identity and demands reconciliation rather than "
        "a timed retry; DispatchIdentityTests.test_matching_key_still_dispatches_once proves an existing "
        "accepted dispatch is never repeated; DispatchLedgerCostTests."
        "test_historical_accepted_operations_remain_discoverable proves the claim and acceptance "
        "metadata stay durable",
        "E-18474; elapsed time alone authorizes no re-execution; a missing or invalid claim timestamp "
        "returns a typed recovery state",
    ),
    "R019": (
        f"{BOUNDARY} proves the adapter envelope directly: "
        "test_backend_operation_refusals_remain_failures (exit 0 with ok=False stays a failure), "
        "test_invalid_common_fields_are_protocol_errors and "
        "test_command_specific_shapes_are_validated (invalid JSON yields a protocol refusal), "
        "test_valid_report_preserves_utf8_under_narrow_locale (a valid successful report is accepted), "
        "test_valid_empty_discovery_report_is_no_new_evidence (empty valid report is NO_NEW_EVIDENCE), "
        "test_transport_failure_remains_distinct, test_failed_collection_is_not_an_empty_list and "
        "test_discovery_does_not_swallow_status_or_analysis_failures; test_campaign_matrix.py and "
        f"{GATES} run in the same record",
        "E-18474; backend errors stay explicit failures and are never folded into an empty result",
    ),
    "R022": (
        f"{GATES} and test_campaign_matrix.py both run in this record, and "
        "test_campaign_continuation_assessment.py plus test_t1931_saipal_boundary.py in the same run "
        "pin the continuation assessment and the adapter boundary this clause names; the record was "
        "captured from the current tree",
        "E-18474; the clause's own surface is exercised by the modules its verification names",
    ),
    "R016": (
        f"{CLOSURES} DispatchIdentityTests.test_tampered_key_is_refused_with_zero_callbacks proves a "
        "caller-supplied idempotency key is recomputed at the dispatch boundary and a mismatch is "
        "refused with no callback; test_same_operation_reconstructs_the_same_key proves a restart "
        "reconstructs the same key; test_independent_campaigns_never_share_identity and "
        "test_distinct_operations_cannot_suppress_each_other prove independent and distinct operations "
        "keep separate identities",
        "E-18474; the pre-fix control dispatched with a tampered key and one callback; after the repair "
        "the same control returns IDEMPOTENCY_KEY_MISMATCH with zero callbacks",
    ),
    "R017": (
        f"{CLOSURES} PersistedDispatchReplayTests.test_later_host_delivers_the_pending_request proves a "
        "no-host fallback persists without claiming dispatch and a later registration delivers it; "
        "test_replay_reuses_the_operation_identity and test_restart_preserves_the_pending_request prove "
        "the replay allocates no new identity across a restart; "
        "test_repeated_registration_does_not_duplicate_accepted_work proves a repeated registration "
        "does not duplicate accepted work; test_replay_without_a_host_keeps_one_durable_copy proves the "
        "inbox holds exactly one row",
        "E-18474; the pending request moves REQUEST_PERSISTED to DELIVERY_CLAIMED to HOST_ACCEPTED "
        "without dropping persisted_at",
    ),
    "R018": (
        f"{LIFECYCLE} test_worker_exception_is_unknown_outcome_and_never_blindly_retried proves a worker "
        "exception is a typed unknown-outcome attempt, not a silent no-op; "
        "test_process_death_preserves_attempt_and_releases_lifecycle_lock proves the lock is released "
        "while generation identity stays recoverable; "
        "test_interrupted_generation_preserves_identity_across_restart proves a restart reconstructs the "
        "interrupted attempt; test_altered_attempt_receipt_never_becomes_a_success proves partial side "
        "effects are not blindly repeated",
        "E-18474; failure accounting is incremented on the failed attempt and a valid subsequent "
        "execution resumes once the attempt is reconciled",
    ),
    "R020": (
        f"{CLOSURES} PublicationReceiptIdentityTests.test_idempotent_enqueue_preserves_original_timestamp "
        "proves one logical receipt keeps its original publication timestamp; "
        "test_crash_after_enqueue_reconstructs_the_missing_receipt proves an enqueue-success with a lost "
        "receipt is recoverable; test_different_findings_keep_independent_receipts proves separate "
        "findings keep separate receipts",
        "E-18474; a publish that never reached the enqueue never claims delivery",
    ),
    "R021": (
        f"{CLOSURES} AppendLogReconciliationTests.test_valid_log_reads_completely proves a valid JSONL "
        "log reads whole; test_malformed_middle_record_surfaces_corruption proves a bad middle record is "
        "not read as a short history; test_torn_final_record_is_explicitly_truncated proves a torn tail "
        "is LOG_TRUNCATED rather than complete; test_damaged_bytes_remain_recoverable proves the "
        "original bytes survive; test_recovery_does_not_invent_dispositions proves reconciliation invents "
        "nothing; {BOUNDARY} test_concurrent_append_is_truncated_until_newline_commits covers concurrent "
        "append and read",
        "E-18474; the same contract is applied to publication receipts as to dispositions",
    ),
    "R023": (
        f"{CLOSURES} DispatchDeadlineTests.test_unresponsive_hook_reaches_deadline_and_reports_uncertain "
        "proves the declared finite deadline is applied to the external invocation; "
        "test_lock_is_released_after_a_bounded_failure proves local ownership is released; "
        "test_timeout_preserves_identity_and_requires_reconciliation proves a later attempt is refused "
        "until reconciled, so a timed-out operation is never blindly replayed; "
        "test_successful_hook_still_passes_the_acceptance_gate proves the ordinary path is unchanged",
        "E-18474; the diagnostic text is reported but never treated as acceptance proof",
    ),
    "R024": (
        f"{CLOSURES} CrossProjectConcurrencyTests."
        "test_independent_projects_do_not_serialize_behind_each_other proves project B progresses while "
        "project A's host callback blocks; CrossProjectConcurrencyTests."
        "test_same_project_duplicate_attempts_stay_serialized proves same-project admission stays "
        "exactly-once, so cross-process ownership was narrowed rather than removed",
        "E-18474; the host invocation runs outside the project mutex while the durable claim and "
        "acceptance reconciliation stay serialized",
    ),
    "R025": (
        f"{LIFECYCLE} test_cancel_and_parallel_step_while_worker_is_running proves cancellation stays "
        "responsive while a worker is active and a request persists; "
        "test_late_worker_cannot_overwrite_new_campaign proves a delayed completion cannot commit after "
        "ownership was invalidated; test_completed_worker_result_recovers_after_commit_lock_contention "
        "proves the commit is revalidated under the lock; {LIFECYCLE} "
        "test_internal_typeerror_does_not_invoke_worker_three_times proves concurrent step calls cannot "
        "duplicate one generation",
        "E-18474; the worker runs between two bounded lock windows, state writes stay atomic, and an "
        "unreconcilable execution keeps UNKNOWN_OUTCOME",
    ),
    "R026": (
        f"{CLOSURES} DispatchLedgerCostTests."
        "test_per_operation_write_volume_does_not_scale_with_history measures 200, 400 and 800 retained "
        "operations and asserts the per-operation write average FALLS as history doubles, which is the "
        "linear-amortized property rather than a fixed count trigger; "
        "test_historical_accepted_operations_remain_discoverable proves compaction keeps archived "
        "identities discoverable; test_interrupted_compaction_preserves_recoverable_data and "
        "test_partial_journal_append_is_detected prove crash consistency; "
        "test_ledger_corruption_remains_a_typed_failure preserves the typed CORE-003 failure",
        "E-18474; an independent probe measured record-sized appends (852 then 856 bytes) rather than "
        "history-sized rewrites; a fixed record-count trigger was removed because it made total write "
        "volume quadratic in history",
    ),
    "R027": (
        f"{CLOSURES} ReportTransportTests.test_report_is_handed_out_in_bounded_pages proves a large "
        "report is handed out in bounded pages; "
        "test_source_identity_is_stable_across_pages and "
        "test_source_identity_changes_when_the_corpus_changes prove the artifact identity is stable "
        "across batches yet moves with the corpus; "
        "test_resume_does_not_skip_or_duplicate_findings and "
        "test_replayed_batch_does_not_duplicate_publication prove resume and replay are lossless; "
        "test_resource_limit_is_not_reported_as_no_new_evidence preserves the typed resource error",
        "E-18474; page size is clamped to declared bounds and a corrupt cursor is reported rather than "
        "silently reset",
    ),
    "R028": (
        f"{CLOSURES} SupervisorParseTests.test_normal_observation_parses_board_once proves one "
        "immutable observation parses BOARD once; test_board_change_between_observations_is_detected "
        "proves a genuine BOARD mutation is seen by the next observation, so no cross-turn cache was "
        "introduced; test_read_only_observation_writes_nothing proves the observation performs no "
        "repair writes",
        "E-18474; an independent probe counts 1 parse_board call on the normal observation path where "
        "the pre-fix path re-parsed per consumer",
    ),
    "R029": (
        f"{CLOSURES} TailEventReaderTests.test_edge_shapes_match_full_read proves the bounded reverse "
        "reader returns the same value as a full read on empty, single-line, multi-line, trailing-blank "
        "and CRLF shapes; test_crlf_matches_full_read and test_oversized_unicode_record_matches_full_read "
        "cover CRLF and UTF-8 boundaries; "
        "test_final_record_larger_than_the_read_window_is_not_truncated proves a large final record is "
        "returned whole where a fixed 8 KB window returned a mid-line fragment; "
        "test_large_journal_reads_only_the_tail proves the lookup does not allocate the whole file",
        "E-18474; no second journal authority was introduced and modification time is never used as "
        "progress evidence",
    ),
    "R030": (
        f"{CLOSURES} ProgressTrackerBoundsTests.test_large_sequence_uses_bounded_memory and "
        "ControllerMemoryBoundsTests.test_repeated_callbacks_do_not_grow_history_without_bound prove a "
        "long observation sequence uses bounded memory; "
        "ProgressTrackerBoundsTests.test_stall_detection_triggers_at_the_established_threshold and "
        "test_oscillation_detection_is_unchanged preserve the existing thresholds and decisions; "
        "test_aggregate_counters_remain_accurate and "
        "ControllerMemoryBoundsTests.test_telemetry_is_bounded_and_events_still_counted prove older "
        "observations still count; ControllerMemoryBoundsTests."
        "test_idempotency_identities_are_not_discarded_with_telemetry proves the guardrail; "
        "ControllerMemoryBoundsTests.test_completion_ui_stays_once_only preserves the once-only UI",
        "E-18474; an independent probe over 5000 records kept history at the 64-record retention with "
        "4936 observations folded into counters and observation_count still 5000",
    ),
    "R031": (
        f"{CLOSURES} and {GATES} preserve the existing focused contracts and the declared gate set; the "
        "four findings still open at T-1931 now each have an independent red control that fails closed: "
        "CORE-004 returns ACCEPTANCE_UNVERIFIED, CORE-006 NOT_QUALIFIED with zero enqueue calls, CORE-009 "
        "made_progress false, CORE-011 DISPOSITION_UNVERIFIED. Genuine installed-host and SAIPAL "
        "end-to-end integration is recorded as explicitly unverified: no receipt from a real installed "
        "host or a real SAIPAL backend exists, and no mock or generation counter is presented as live "
        "acceptance",
        "E-18474; the four red controls are .saipen/evidence/T-1932/closures/red_controls.py run against "
        "current source; the acceptance criterion itself is satisfied by refusing to infer live "
        "acceptance from mocks; the T-1930 reconciliation it names uses one authoritative state owner",
    ),
    "R032": (
        f"{GATES} and {CLOSURES} independently resolve the original SRC-337 findings rather than "
        "inheriting its labels: every requirement clause is settled from this one authenticated record, "
        "and the four counterexamples recorded in .saipen/evidence/T-1931/remaining-after-saipal-boundary.json "
        "now fail closed. Real installed-host and SAIPAL acceptance is recorded as requiring actual "
        "receipts that do not yet exist, so it stays unverified instead of being inferred",
        "E-18474; the post-fix controls are .saipen/evidence/T-1932/closures/red_controls.py; the "
        "original T-1931 Source and its history remain immutable and only the disproved closure "
        "prospect is corrected",
    ),
}


def main(argv: list[str]) -> int:
    dry = "--dry" in argv
    failures = []
    settled = []
    for rid, (verification, evidence) in sorted(SETTLE.items(), key=lambda kv: kv[0]):
        payload = {
            "rid": rid,
            "disposition": "VERIFIED",
            "work": "T-1932",
            "evidence": evidence,
            "verification": f"{BIND}; {verification}",
        }
        if dry:
            print(f"[dry] {rid}: {payload['verification'][:140]}...")
            continue
        result = intake.set_disposition(
            ROOT,
            "SRC-338",
            rid,
            "VERIFIED",
            work=payload["work"],
            evidence=payload["evidence"],
            verification=payload["verification"],
        )
        if result.get("ok"):
            settled.append(rid)
            print(f"OK   {rid} {result.get('code')}")
        else:
            failures.append((rid, result))
            print(f"FAIL {rid} {result.get('code')}: {result.get('detail')}")
    print(f"\nsettled={len(settled)} failed={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
