# T-1587 — post-fix evidence

## Change

1. `tools/saipen_engine/reconcile.py` `_board_lifecycle_repairs`: new
   deterministic class `stale-closure-metadata` — a parseable row under
   ## TODO / ## DOING / ## BLOCKED carrying any `board.CLOSURE_METADATA_FIELDS`
   key gets a `claim-clear` atom removing exactly those keys (the same
   vocabulary `_reopen_field_removals` strips on the T-1572 DONE reopen).
   A row that repeats a known field is an ambiguous record: the atom carries
   `refuse: True` and no value is silently chosen.
2. `tools/saipen_engine/reconcile.py` `_combined_decisions`:
   `--attest-legacy-done` now answers ONLY `legacy-done-review` refusals.
   Before, any refused lifecycle ticket was swept into the flag, advertising
   a command that could not commit (the T-1363 defect shape).

The validation rule itself (`closure_metadata_errors`, board.py) is untouched
and stays armed: ordinary mutators still refuse the malformed board
(`test_ordinary_mutation_still_refuses_before_the_repair`).

## Route (no new CLI surface)

    saipen recover
      -> RECONCILE_REAUTH_REQUIRED, repair_id,
         canonical_next_command: saipen recover --apply-approved-repair <id>
    saipen recover --apply-approved-repair <id>
      -> journaled reconcile commit (op id, receipt, board target,
         strict validate_texts on the proposal, defect_delta: introduced=0)
      -> REPAIRED
    saipen recover -> CLEAN ; replay -> STALE_APPROVED_REPAIR

## Gates

- `python -B -m unittest test_t1587_stale_closure_recovery` — 23/23 OK
  (pre-fix red control: 14 red, 9 green — `red-control-prefix.txt`)
- neighbors: test_t1572_ticket_scoped_recovery, test_legacy_lifecycle_compat,
  test_t1533_terminal_handback, test_intent_audit_fixes,
  test_recovery_reachability — 175 OK (3 skipped)
- closure vocabulary: test_closure_provenance, test_ticket_supersession,
  test_log_tail_quarantine — 69 OK
- ruff on both changed files: PASS; py_compile PASS
- canonical validator: the two FAILs are `runtime manifest names a file git
  does not track` -- one is this Work's own new test file (clears at commit),
  one is `tools/test_improve_error_boundary.py`, an untracked in-flight test
  of a CONCURRENT seat (created 01.10 20:14; improve.py/saipen.py/journal.py
  edited by that seat in the same window) that this Work is not authorized
  to commit or delete. The ship-gate variant of the same validator
  deliberately excludes foreign untracked noise, so this does not block a
  scoped release.
- portable floor tests/validate.sh: PASS.
- core-unit family (unit), record
  `.saipen/evidence/core-unit/e7216f49334d29d9-20261001T181415Z.json`
  (UNCITED -- the run refused certification because the shared tree kept
  changing under it: a concurrent seat edited improve.py/saipen.py/journal.py
  mid-run): ran 4608, 6 red. Decomposition, re-run live:
  - 3x test_t1412_conformance_truth + 2x test_concurrency_independence
    LiveTree control: PASS on the settled tree (transient reds of the
    mid-edit snapshot).
  - 1x test_style_contract_chokepoint evidence-marker scan: still red, but
    the failure message itself names the cause -- untracked evidence
    directories of OTHER tickets (T-1581/T-1582/T-1585/T-1586 candidates)
    left in the tree by their seats; not this Work's surface, not this
    Work's to delete.
  - introduced-by-T-1587 reds: 0 (focused 23/23 green twice, incl. after
    the concurrent seat's journal.py change; 175 neighbor + 69 closure
    neighbor tests green).
- tools/run_scenarios.py full pass (01.10, shared-machine run, >60 min):
  5 FAILED lines, all inside the inline release-executor probes (steps
  14/15); step 15's refusal detail names `cross-doc drift
  [improve-command-parity]` -- the same concurrent seat's in-flight
  improve.py/REGISTRY change. Isolated re-run: see the final report of
  this Work in .saipen/LOG.md (same day).
