# T-1803 / SRC-261 — Archived Improve-Cycle Reconciliation Report

## 1. STATUS

`COMPLETE` (engine mission `T-1803` / `SRC-261`). The archived improve-cycle reconciliation deadlock is resolved in the SAIPEN engine via an append-only retrospective successor ledger outside original cycle directories, with full multi-seat liveness, native journal provenance (`retrospective-` op class and `improve_retrospective_v1` verification policy), and zero mutation of historical reports or the consumer repository (`V:\___VAC\__K\__CODE\_PY\_AUDAPACK`).

## 2. AUTHORITY

- **Engine Repository**: `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN` (`HEAD` `fc160681de00c1e9568ff36835df8578dc5bd680`, version `1.88.0`).
- **Active Ticket & Source**: `T-1803` (`SRC-261`, 33 actionable clauses `SRC-261:R001`..`R033`), owner `saipen-cli`.
- **Continuation & Safety Valve**: `continuation_authority: operator_required`, `authority_source: E-16134`, `authority_until: budget`, `safety_valve_mode: hard_wait`. No operator authority or safety-valve reset was derived from the handoff prompt.
- **Consumer Boundary**: `V:\___VAC\__K\__CODE\_PY\_AUDAPACK` (`lineage-79944d6c0334416ebe1001e97de6c1cc`, `last_event: 3368`, `T-311` `BLOCKED`) remained strictly read-only throughout. Pre/post SHA-256 digests of all protected consumer files (`STATE.md`, `BOARD.md`, `LOG.md`, and both archived improve cycles) are verified identical in `.saipen/evidence/T-1803-archived-improve/baseline-observation.json` and `.saipen/evidence/T-1803-archived-improve/historical-restart-acceptance.json`.

## 3. ROOT CAUSE

Direct source inspection of `tools/improve.py` and `tools/saipen_engine/continue_fallback.py` (the handoff's `tools/saipen_engine/improve.py` path does not exist; `tools/improve.py` is the canonical owner) and reproduction on disposable copies of `imp-vacterro-audapack-20260918-1` and `imp-vacterro-audapack-20260919-7` established five interacting defects:

1. **Terminal-status short-circuit in `reconcile_cycle()`**: `tools/improve.py` classified seats (`EMPTY_DRAFT`, `STILL_ACTIONABLE`, etc.) when `cycle_status` was `archived` (`TERMINAL_CYCLE_STATUSES`), but immediately returned `code: "ALREADY_TERMINAL"` without retiring empty drafts, recording retrospective dispositions, or surfacing a bounded external blocker when `SWEEP.md` was absent or incomplete.
2. **Archived mutation refusal without a retrospective successor**: `write_sweep_entry()`, `retire_seat()`, `complete_report()`, and `abort_cycle()` rejected `cycle_status: archived` to protect archive immutability, while `_require_cycle_amendable()` allowed `--amend` only when a prior `SWEEP.md` disposition already existed for the finding. Consequently, an archived cycle with committed findings in `saipen_improve_*.md` and no `SWEEP.md` had no legal first-disposition path.
3. **Single-seat liveness blindness in `cycle_liveness()`**: `tools/saipen_engine/continue_fallback.py` inspected only `seats[0]` (primary seat), hiding unfinished or actionable findings in secondary seats (`saihunt-01`, `saipython-01`, `saiwiki-01`) and repeatedly advertising archived empty drafts (`EMPTY_DRAFT`) as stale work with no finite exit.
4. **Absence of a canonical retrospective evidence store**: Modifying `MANIFEST.md`, `saipen_improve_*.md`, or creating a synthetic `SWEEP.md` inside `.saipen/improve/<cycle_id>/` would falsify historical archive state. No append-only successor outside the immutable cycle directory existed.
5. **Journal writer provenance registration**: Minting `retrospective-<32hex>` operation IDs in `tools/saipen_engine/improve_retrospective.py` required registering `"retrospective-"` under `_HEX32` in `tools/saipen_engine/journal.py` (`OP_CLASSES`) so `test_t1577_op_id_provenance` verifies writer class registration alongside `RETROSPECTIVE_POLICY` (`improve_retrospective_v1`).

## 4. ARCHITECTURAL FIX

1. **Append-Only Successor Outside Original Cycles (`tools/saipen_engine/improve_retrospective.py`)**:
   - Stores retrospective reconciliation records at `.saipen/improve-reconciliation/<cycle_id>.jsonl` (`SUCCESSOR_ROOT_REL`), leaving `.saipen/improve/<cycle_id>/` byte-identical.
   - Line 1 (`kind: "header"`, `schema: "saipen.improve.retrospective.v1"`) binds `lineage_id`, `cycle_id`, `original_status`, `manifest_sha256`, `sweep_present`, `sweep_sha256`, per-seat report hashes/findings, and `history_sha256`.
   - Subsequent lines (`kind: "event"`) form a SHA-256 hash chain (`sequence`, `previous`, `operation_id`, `sha256`) recording `disposition` (`INVALID`, `NOT_REPRODUCED`, `DEFERRED`, `NEEDS_EXTERNAL_EVIDENCE`), `seat_retirement` (`EMPTY_DRAFT`, `ABANDONED_NO_FINDINGS`, `BLOCKED_EXTERNAL`), and `reconciliation` outcomes (`RECONCILED_RETROSPECTIVE`, `RETIRED_EMPTY_ARCHIVE`, `BLOCKED_EXTERNAL`).
   - Current-authority minting (`CONFIRMED`) from archived drafts is explicitly refused (`RETROSPECTIVE_CONFIRMED_FORBIDDEN`). Resolved historical dispositions (`INVALID`, `NOT_REPRODUCED`, `DEFERRED`) require owned repository-relative verification evidence (`--verification`) hashed into `verification_sha256`.
   - Each append carries a compare-and-swap `base_successor_sha256` precondition and validates native committed journal receipts (`operation_id` prefix hash match in `.saipen/ops/committed/` or `.saipen/ops/compacted.jsonl`), preventing forged hash chains, lost updates, or stale plan overwrites.
2. **Canonical Journal & Recovery Integration (`tools/saipen_engine/journal.py`, `tools/improve.py`)**:
   - Registered `RETROSPECTIVE_POLICY = "improve_retrospective_v1"` in `VERIFICATION_POLICIES` and `"retrospective-"` in `OP_CLASSES`.
   - Extended `verify_improve()` to dispatch `.saipen/improve-reconciliation/*.jsonl` targets to `verify_successor_bytes()`, enforcing schema, hash-chain, and immutable original-history bindings during both normal execution and `auto_recover_pending()` crash recovery.
   - Routed retrospective writes through `improve._journaled_write(..., op_class="retrospective", verification_policy=RETROSPECTIVE_POLICY, extra_dependencies=...)` under `project_writer_lock(project_root)`.
3. **All-Seat Liveness & CLI Integration (`tools/saipen_engine/continue_fallback.py`, `tools/saipen.py`)**:
   - Updated `cycle_liveness()` to evaluate all seats via `retrospective_status()`, preserving legacy primary-seat keys (`seat_id`, `report_status`) while exposing `seat_summaries`, `pending_findings`, `blocked_findings`, `retrospective_reconciled`, and `retrospective_outcome`.
   - Added `--retrospective` to `saipen improve sweep` and `saipen improve retire`; updated `saipen improve reconcile` and `saipen improve sweep-queue` to process terminal cycles through the retrospective successor.
   - Protected `.saipen/improve-reconciliation/` in `tools/saipen_engine/admission.py` (`PROTECTED_CANONICAL_NAMESPACE`) and `tools/saipen_engine/capability.py` (`guard_core_mutation`).

## 5. EXACT CHANGED SYMBOLS

- `tools/saipen_engine/improve_retrospective.py` (new module):
  - `SUCCESSOR_ROOT_REL`, `SUCCESSOR_SCHEMA`, `RETROSPECTIVE_POLICY`, `RESOLVED_DISPOSITIONS`, `PENDING_DISPOSITIONS`, `ALLOWED_RETROSPECTIVE_DISPOSITIONS`, `RETROSPECTIVE_RETIRE_REASONS`
  - `successor_path()`, `is_successor_rel()`, `is_terminal_manifest()`, `capture_original_snapshot()`, `original_dependency_specs()`, `verify_successor_bytes()`, `load_validated_successor()`, `retrospective_status()`, `plan_retrospective_disposition()`, `plan_retrospective_seat_retirement()`, `plan_retrospective_reconcile()`
- `tools/improve.py`:
  - `_require_retrospective_mutation_admitted()`, `_journaled_write()`, `_retrospective_write()`, `_write_retrospective_sweep_entry()`, `write_sweep_entry()`, `retire_seat()`, `reconcile_cycle()`, `sweep_queue()`, `_build_parser()`, `main()`
- `tools/saipen_engine/continue_fallback.py`:
  - `cycle_liveness()`, `_legacy_SingleSeat_liveness()`, `with_cycle_liveness()`
- `tools/saipen_engine/journal.py`:
  - `RETROSPECTIVE_POLICY`, `VERIFICATION_POLICIES`, `OP_CLASSES` (`"retrospective-"` under `_HEX32`), `verify_improve()`
- `tools/saipen_engine/admission.py`:
  - `_PROTECTED_SAIPEN_PREFIXES` (`.saipen/improve-reconciliation/`)
- `tools/saipen_engine/capability.py`:
  - `_CORE_PROTECTED_PREFIXES` (`improve-reconciliation/`)
- `tools/saipen.py`:
  - `_public_improve()` (`--retrospective` flag forwarding for `sweep` and `retire`)
- `saipen/IMPROVE.md`:
  - Documented retrospective archive reconciliation rules and `.saipen/improve-reconciliation/<cycle_id>.jsonl` contract.
- `tools/test_t1803_archived_improve.py` & `tools/test_t38_improve_cycle_liveness.py`:
  - 35 focused RED-to-GREEN semantic controls and updated empty-draft liveness assertions.

## 6. RED/GREEN TEST RESULTS

- **Pre-Implementation RED (`E-16191`, `.saipen/evidence/T-1803-archived-improve/RED-full.txt`)**:
  - `tools/test_t1803_archived_improve.py` ran 23 controls against the pre-fix engine: **12 failures, 9 errors** (2 baseline guard controls passed), reproducing the archived reconciliation deadlock, missing first-disposition path, and multi-seat liveness blindness.
- **Post-Implementation GREEN (`.saipen/evidence/T-1803-archived-improve/GREEN-final-focused.txt`)**:
  - `tools/test_t1803_archived_improve.py`: **35/35 PASS** (`OK` in 42.1s).
- **Native Anchored Regression Execution (`saipen work regression T-1803`)**:
  - Fixed verifier `tools/test_t1803_archived_improve.py` (`verifier: 686b423b186f9d96f6a2a9d3e495899b33c15bd3eff69e3c03c153353e73d79a`, receipt `.saipen/evidence/regression/regression-execution-361a80942197422888824e0901910756.json`) failed on the preserved pre-fix subject (`before.subject: 860c1fe6ec72e6db8e88534acadcb8219d96340b02ff847fc2af44d47db09ad6`, `ran: 35, failed: 31` at `E-16198`) and passed on the post-fix subject (`after.subject: ad6bbb6e91e29de05c7c1789b427f79492c5715536cd4b00e2d223c38de68484`, `ran: 35, failed: 0` at `E-16199`).

## 7. FULL REGRESSION RESULTS

- **Focused & Neighboring Suites**:
  - `tools/test_t1803_archived_improve.py`: **35/35 PASS**
  - `tools/test_improve_reconcile.py`, `tools/test_t321_improve_Lock_reconcile.py`, `tools/test_t1115_improve_amend.py`, `tools/test_t1273_improve_abort_clean.py`: **34/34 PASS** (`GREEN-final-improve-neighbors.txt`)
  - `tools/test_t38_improve_cycle_liveness.py`: **11/11 PASS**
  - `tools/test_t1577_op_id_provenance.py`: **26/26 PASS** (including `RegistryCoversEveryWriter.test_every_literal_writer_class_is_registered` and `test_every_named_writer_class_is_registered` after registering `"retrospective-"` in `journal.OP_CLASSES`)
  - `tools/test_t1571_lint_surface.py`: **PASS** (Ruff 0.16.0 clean across `tools/` and `tests/`, zero trailing whitespace)
- **Full Core-Unit Family (`tools/core_unit.py evidence T-1803`)**:
  - Initial run at `E-16197` (`de39bbd33e86d519-20261016T184906Z.json`) ran 6,791 unit tests and caught `new_red: 2` in `test_t1577_op_id_provenance.py` due to unregistered `"retrospective-"` in `journal.OP_CLASSES`.
  - Repaired in `tools/saipen_engine/journal.py` and re-verified across the declared unit family.

## 8. RESTART ACCEPTANCE

Recorded in `.saipen/evidence/T-1803-archived-improve/historical-restart-acceptance.json`:

1. **Disposable Copy of `imp-vacterro-audapack-20260918-1` (2 seats: `saihunt-01` empty draft, `saipython-01` complete with 4 findings `SAIPYTHON-1/IMP-001..004`)**:
   - Before reconciliation: `reconcile_cycle` returned `BLOCKED_EXTERNAL` (`RECONCILE_PENDING_FINDINGS`), exposing all 4 findings in `saipython-01` while retiring `saihunt-01` (`EMPTY_DRAFT`).
   - Recorded `NEEDS_EXTERNAL_EVIDENCE` on the disposable copy for `SAIPYTHON-1/IMP-001..004` via `--retrospective`; `reconcile_cycle` persisted `outcome: "BLOCKED_EXTERNAL"` with `pending_findings: []`, `blocked_findings: 4`, `stale: false`.
   - Fresh subprocess restart (`python -B -c ... cycle_liveness`) observed identical persisted state (`blocked: true`, `stale: false`, `pending_findings: []`, `blocked_findings: 4`).
   - Original cycle files (`MANIFEST.md`, `saihunt-01/saipen_improve_SAIHUNT.md`, `saipython-01/saipen_improve_SAIPYTHON.md`) remained byte-identical (`original_sweep_exists: false`).
2. **Disposable Copy of `imp-vacterro-audapack-20260919-7` (4 seats: `saihunt-01` complete with `SAIHUNT-1/IMP-001`, `saipython-01` complete with `SAIPYTHON-1/IMP-001`, `saiwiki-01` complete with 0 findings, `probe-01` empty draft)**:
   - Before reconciliation: `reconcile_cycle` retired `probe-01` (`EMPTY_DRAFT`) and exposed both `SAIHUNT-1/IMP-001` and `SAIPYTHON-1/IMP-001`.
   - Recorded `NEEDS_EXTERNAL_EVIDENCE` on the disposable copy for both findings via `--retrospective`; `reconcile_cycle` persisted `outcome: "BLOCKED_EXTERNAL"` with `pending_findings: []`, `blocked_findings: 2`, `stale: false`.
   - Fresh subprocess restart confirmed identical persisted state and zero original-file mutation (`original_sweep_exists: false`).
3. **Live Consumer (`V:\___VAC\__K\__CODE\_PY\_AUDAPACK`) Verification**:
   - `consumer_unchanged: true`; all SHA-256 digests in `AUDAPACK` match `baseline-observation.json` byte-for-byte.

## 9. FORENSIC EVIDENCE POLICY

Recorded in `.saipen/evidence/T-1803-archived-improve/FORENSIC-POLICY.md` and `.saipen/evidence/T-1803-archived-improve/manifest-policy-observation.json`:

- **Current Contract v3 Behavior**: `tools/saipen_engine/audit_manifest.py` (`MANIFEST_CONTRACT_VERSION = 3`) does not include `.saipen/improve/` or `.saipen/improve-reconciliation/` in `CONDITIONAL_EXPORT_DIRS` or `OPTIONAL_EXPORT_DIRS`. Although `is_exportable()` (an exclusion predicate) returns `True` for non-secret paths under `.saipen/improve/`, directory selection omits them by design. `audit_manifest.py` is preserved byte-identical to its pre-mission snapshot (`accb9c8770dbbcd2d5ec0bc776c3f9a2b156b81b3d2eed5c1b19919511c1b774`).
- **Bounded Opt-In Class Definition (`improve_forensics_v1`)**: Defined a non-authoritative, opt-in forensic adjunct bounded to at most 8 explicitly selected cycles, 32 seats, 128 findings, 2 MiB total, and 128 KiB per report, carrying cycle/seat metadata, composite finding IDs, original SHA-256 digests, and successor event receipts while excluding credentials, transient locks/staging, and machine-local roots. Deployment requires an explicit future contract-version bump (`v4`) and independent consumer admission.

## 10. CROSS-PROJECT REGRESSION ASSESSMENT

- **AUDAPACK (`V:\___VAC\__K\__CODE\_PY\_AUDAPACK`)**: Read-only (`lineage-79944d6c0334416ebe1001e97de6c1cc`, `E-3368`, `T-311` `BLOCKED`). Once this SAIPEN engine change is promoted to the shared runtime (`C:\ProgramData\SAI\SAIPEN`) in an authorized release wave and an admitted AUDAPACK session runs, AUDAPACK can reconcile `imp-vacterro-audapack-20260918-1` and `imp-vacterro-audapack-20260919-7` via `saipen improve sweep ... --retrospective` and `saipen improve reconcile <cycle_id>` without touching historical report files.
- **Active & Genuinely Complete Cycles Across All Projects**: Verified by `test_current_active_cycle_is_not_a_retrospective_target`, `test_genuinely_complete_cycle_keeps_existing_terminal_behavior`, and all 34 neighboring Improve tests (`test_improve_reconcile.py`, `test_t321_improve_lock_reconcile.py`, `test_t1115_improve_amend.py`, `test_t1273_improve_abort_clean.py`). Active cycles continue to refuse retrospective mutation; completed cycles with no pending findings return `ALREADY_TERMINAL` without creating successor files.

## 11. REMAINING BLOCKERS

- **T-1803 (Engine)**: None. All 33 clauses of `SRC-261` are satisfied and verified.
- **AUDAPACK `T-311` (External Consumer)**: Remains `BLOCKED` in `V:\___VAC\__K\__CODE\_PY\_AUDAPACK` by design (`SRC-261:R002`). The 6 historical findings across `imp-vacterro-audapack-20260918-1` (`SAIPYTHON-1/IMP-001..004`) and `imp-vacterro-audapack-20260919-7` (`SAIHUNT-1/IMP-001`, `SAIPYTHON-1/IMP-001`) require disposition in an admitted AUDAPACK session after runtime promotion.

## 12. NEXT EXACT ACTION

Complete `T-1803` verification/review/local-closure in `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`, then run `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\bin\saipen.cmd --project-root V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN continue --json` to advance to the next canonical `cc all` item (`SRC-262`).

---

## Requirement-to-Evidence Audit (`SRC-261:R001`..`R033`)

| Clause | Disposition | Evidence & Verification |
| :--- | :--- | :--- |
| `SRC-261:R001` | `VERIFIED` | `.saipen/evidence/T-1803-archived-improve/baseline-observation.json`, `.saipen/STATE.md` (`E-16185`..`E-16188`) |
| `SRC-261:R002` | `VERIFIED` | `.saipen/evidence/T-1803-archived-improve/historical-restart-acceptance.json` (`consumer_unchanged: true`) |
| `SRC-261:R003` | `VERIFIED` | `.saipen/evidence/T-1803-archived-improve/baseline-observation.json`, `tools/improve.py`, `tools/saipen_engine/continue_fallback.py` |
| `SRC-261:R004` | `VERIFIED` | `.saipen/evidence/T-1803-archived-improve/baseline-observation.json` (6 composite findings across both cycles) |
| `SRC-261:R005` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_ordinary_archived_mutators_remain_forbidden`), `historical-restart-acceptance.json` |
| `SRC-261:R006` | `VERIFIED` | `tools/saipen_engine/improve_retrospective.py`, `tools/improve.py` (`_write_retrospective_sweep_entry`, `reconcile_cycle`) |
| `SRC-261:R007` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_committed_unresolved_findings_cannot_round_up_to_success`, `test_needs_external_evidence_stays_visible_without_endless_actionable_retry`) |
| `SRC-261:R008` | `VERIFIED` | `tools/saipen_engine/improve_retrospective.py` (`retrospective_status`), `tools/saipen_engine/continue_fallback.py` (`cycle_liveness`) |
| `SRC-261:R009` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_conflicting_duplicate_disposition_never_overwrites`, `test_concurrent_dispositions_preserve_both_findings_after_bounded_retry`, `test_stale_disposition_plan_cannot_overwrite_an_intervening_commit`) |
| `SRC-261:R010` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_interrupted_append_recovers_without_mutating_original_cycle`, `test_fresh_process_crash_after_verified_rolls_forward`) |
| `SRC-261:R011` | `VERIFIED` | `tools/saipen_engine/improve_retrospective.py`, `tools/saipen_engine/journal.py` (`RETROSPECTIVE_POLICY`) |
| `SRC-261:R012` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_empty_archived_draft_retires_without_touching_original_files`) |
| `SRC-261:R013` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_partially_completed_multi_seat_cycle_exposes_non_primary_findings`) |
| `SRC-261:R014` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_committed_unresolved_findings_cannot_round_up_to_success`) |
| `SRC-261:R015` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_missing_sweep_acquires_first_retrospective_disposition_outside_archive`) |
| `SRC-261:R016` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_partial_sweep_preserves_committed_entries_and_tracks_remainder`) |
| `SRC-261:R017` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_exact_duplicate_disposition_is_idempotent`, `test_conflicting_duplicate_disposition_never_overwrites`) |
| `SRC-261:R018` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_concurrent_dispositions_preserve_both_findings_after_bounded_retry`, `test_stale_disposition_plan_cannot_overwrite_an_intervening_commit`) |
| `SRC-261:R019` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_original_history_change_invalidates_successor_binding`, `test_recovery_refuses_changed_original_dependency`) |
| `SRC-261:R020` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_wrong_lineage_cannot_reuse_successor`) |
| `SRC-261:R021` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_missing_admission_refuses_at_existing_public_boundary`, `test_missing_active_work_is_not_retrospective_admission`) |
| `SRC-261:R022` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_foreign_actor_cannot_mutate_claimed_project_history`, `test_producer_cannot_write_successor_canonical_evidence`) |
| `SRC-261:R023` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_interrupted_append_recovers_without_mutating_original_cycle`, `test_fresh_process_crash_after_verified_rolls_forward`) |
| `SRC-261:R024` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_fresh_process_sees_persisted_reconciliation`), `historical-restart-acceptance.json` |
| `SRC-261:R025` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_reconciled_archive_stops_repeated_advertisement`, `test_public_cli_sweep_reconcile_queue_and_repeated_continue`) |
| `SRC-261:R026` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_current_active_cycle_is_not_a_retrospective_target`), `GREEN-final-improve-neighbors.txt` |
| `SRC-261:R027` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_genuinely_complete_cycle_keeps_existing_terminal_behavior`) |
| `SRC-261:R028` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_no_go_binding_brake_refuses_retrospective_mutation`) |
| `SRC-261:R029` | `VERIFIED` | `tools/test_t1803_archived_improve.py` (`test_successor_namespace_is_protected_from_direct_file_tools`, `test_forged_valid_hash_chain_without_native_writer_receipt_is_blocked`, `test_archived_draft_cannot_mint_current_confirmed_authority`) |
| `SRC-261:R030` | `VERIFIED` | `.saipen/evidence/T-1803-archived-improve/FORENSIC-POLICY.md`, `.saipen/evidence/T-1803-archived-improve/manifest-policy-observation.json` |
| `SRC-261:R031` | `VERIFIED` | `.saipen/evidence/T-1803-archived-improve/GREEN-final-focused.txt`, `GREEN-final-improve-neighbors.txt`, `tools/test_t1577_op_id_provenance.py`, `tools/core_unit.py` |
| `SRC-261:R032` | `VERIFIED` | `.saipen/evidence/T-1803-archived-improve/historical-restart-acceptance.json`, `tools/test_t1803_archived_improve.py` |
| `SRC-261:R033` | `VERIFIED` | `.saipen/evidence/T-1803-archived-improve/REPORT.md`, `.saipen/evidence/T-1803-archived-improve/DESIGN.md`, `.saipen/evidence/T-1803-archived-improve/FORENSIC-POLICY.md` |
