# T-1439 / T-1440 — finite conformance routing, verified current bytes

Verified 2026-09-21 by the continuation session holding T-1441 (SRC-098). This
report is the artifact the roadmap names at its T-1440 row; it records the
current repair evidence and its limits. It does not claim repository-wide
release readiness, installed delivery or publication.

## What the repair is

- The immutable conformance receipt binds the COMPLETE classified blocking
  finding set (`blocking_findings`, status `complete` or `unavailable`), not a
  truncated warning tail.
- `conformance_decision` resolves a receipt-bound CURRENT_FAIL to exactly one
  of: a registered executable repair, a refresh (`saipen validate`) for
  stale/missing evidence, or a terminal engineering diagnosis
  (`ENGINEERING_REQUIRED`) when no registered repair exists.
- `saipen validate` is never advertised as the repair for a CURRENT_FAIL.
- Router/continue/status/explain-next/automation consult the same decision, so
  a red gate no longer routes back into validate.
- Stale, tampered and moved receipts remain fail-closed; carried-debt Work
  PASS never becomes global conformance PASS.

Files carrying the change: `tools/saipen_engine/conformance.py`,
`tools/saipen_engine/router.py`, `tools/saipen_engine/automation.py`,
`tools/saipen.py`, `tools/validate.py`, the T-1439 additions in
`tools/test_conformance_repair_boundary.py`, plus registry/command/effect/docs
parity rows touched by the same slice.

## Acceptance evidence (operator list 1-8)

Materialized current runtime (runtime manifest + repository test resources, no
source substitutions) with a hermetic environment; 10 modules, 109 tests:

    python -B -m unittest -v tools.test_conformance_repair_boundary \
        tools.test_t1412_conformance_truth tools.test_src085_conformance_disposition \
        tools.test_validator_findings tools.test_remediation_self_consistency \
        tools.test_continue_chain tools.test_protocol_registry \
        tools.test_source_quarantine_route tools.test_source_multiwork tools.test_debt_gate

Result: `Ran 109 tests ... OK` (`t1439-current-family-20260921.log`, 2026-09-21). The
same family on the pre-final materialization failed only on the
`command_resolution` load budget (41690 > 40960); the current bytes pass
(`t1439-budget.log`, and the 109-run above).

Mapping:

1. CURRENT_FAIL + registered repair routes to it:
   `RepairBoundaryTests.test_registered_repair_remains_executable_but_validate_is_not_a_repair`,
   `RouterConformanceGateTests.test_named_remediation_is_executable_and_clears_the_refusal`.
2. CURRENT_FAIL without a registered repair reaches a terminal diagnosis:
   `test_current_fail_without_registered_repair_has_terminal_diagnosis`.
3. No validate -> validate loop:
   `test_stale_fail_refreshes_instead_of_executing_its_old_repair`,
   `IdleGateTests.test_current_failure_does_not_recommend_another_idle_validation`.
4. Complete blocking identity set in JSON:
   `test_every_blocking_record_survives_duplicate_family_keys`,
   `RealValidatorBoundaryTests.test_real_source_and_flat_cli_preserve_findings_and_stop_the_loop`,
   `test_classifier_failure_is_unavailable_not_an_empty_complete_set`.
5. Stale/invalid receipts fail closed:
   `test_tampered_blocking_findings_cannot_be_current_evidence`,
   `ValidateSurfaceTests.test_moved_source_pass_never_certifies_the_new_source`,
   `test_receipt_write_failure_cannot_return_valid`.
6. Carried-debt Work PASS is not global PASS:
   `test_strict_core_stays_red_with_carried_debt`,
   `test_carried_unrelated_problem_passes_but_keeps_release_blocked`.
7. status / next / continue / explain-next / automation agree:
   `StatusSurfaceTests.test_explain_next_agrees_with_status_and_next_on_a_red_gate`,
   `test_status_exposes_the_disposition_and_stops_advertising_continue`,
   `test_status_matrix_json_and_human_agree_with_authority`,
   `test_clean_conformance_keeps_continue_in_the_automation_block`.
8. Read-only diagnostics remain admitted at DONE:
   `IdleGateTests.test_active_work_route_is_not_owned_by_the_idle_gate`,
   `test_clean_conformance_keeps_ordinary_continuation`, and the boundary test's
   `next/continue/status/explain-next` probes, which complete without tracebacks
   and without writing receipt files.

Issue instrument: on the pre-fix materialization the new module is red with 5
failures + 6 errors (`t1439-control-red.log`, `control-pair.json`); on the
fixed bytes the module is 9/9 OK (`t1439-control-green.log`). The pre-fix red
run pins that the oracle detects exactly the defect class this ticket exists
for.

Focused static checks: `python -m ruff check tools/ tests/` PASS
(`t1439-ruff.log`).

## Open boundaries and classification

- PATCH_OWNED in the hermetic family: 0. UNKNOWN: 0.
- DEFECT (new, T-1442): with `SAIPEN_HOST_SESSION` set, finishing a child in
  the T-1436 chain fixture leaves the resumed parent DOING-claimed, the
  continue trace drops the adoption step, and
  `tools.test_continue_chain` / `tools.test_conformance_repair_boundary` fail
  inside a live host session while passing without the carrier.
  `test_hermetic_env.isolate_host_session` does not strip that carrier.
- PRE_EXISTING (documented in the T-1438 report): the live HOME root carries
  three incoming SAIHANDOFF reports that fail `root-file-set` and coverage
  checks, and three untracked regression modules that owe packaging. Running
  validator-dependent fixtures from the live root therefore reports the
  root-file-set finding; the materialized fixture oracle is unaffected.
- Delivery limits: the implementation is uncommitted in the dirty worktree;
  installed-runtime parity and live host acceptance are not established;
  publication remains paused. Do not round this to release-ready.

## Verified byte identity

- Source: repository root `V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN`,
  HEAD `d97abdc097db432bafe2316b1e3577e44cd9cc4c` plus the dirty slice above.
- The verification materializes the current runtime manifest, so a later
  source edit invalidates this report until re-run; the next session should
  re-materialize rather than trust this snapshot.
