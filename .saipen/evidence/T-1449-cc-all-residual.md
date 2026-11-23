# T-1449 (`cc all`) -- measured residual state at BUILD exit

Ticket verify: "cc all is complete and the repository-declared verification
harness passes". Measured 2026-11-13 on working tree over HEAD `66ef622a4`.

## Declared harness

| command | result |
| --- | --- |
| `python tools/validate.py` | FAILED, exit 1, **23 problem(s) / 33 warning(s)** |
| `python -m ruff check tools/ tests/` (ruff 0.16.0, the pinned version `ruff.toml` and `validate.yml` name) | **557 errors** (394 E501, 51 E402, 35 F401, 14 PLW0108, 13 SIM117, 12 RUF059, 11 F841, 8 RUF100) |
| `python tools/core_unit.py evidence T-1449` | not executed: the binding ship gate routes a focused citation, and the full family is the red set recorded in E-20987 (8443 tests / 132 new red) |

The ruff failures are on files the working tree carries but HEAD does not
(`tools/test_campaign_matrix.py M`, `tools/saipen_engine/intake.py M`,
`tests/test_producer_effect_truth.py ??`), i.e. the uncommitted work blob.

## The 23 validator problems, by cause

1. **Unresolved source receipts on DONE Work (3).**
   `FAIL: source receipts -- DONE Work T-1606 has unresolved source receipt SRC-167`,
   same for T-1961/SRC-407 and T-1964/SRC-410. Measured coverage state:
   - SRC-167 (external_audit): 9 actionable clauses, all `disposition: UNKNOWN`
     (R001..R009). Required: `saipen source disp SRC-167:SRC-167:R0NN <TERMINAL>
     --work T-1606 --evidence ... --verification ...`.
   - SRC-407 (user_instruction): 1 actionable clause, `run saihunt at current
     epoch`, `UNKNOWN`. Body verbatim: `T-1961: run saihunt at current epoch`.
   - SRC-410 (user_instruction): **0 requirements, 0 actionable**. With no
     captured clause `intake.coverage_complete` returns False forever
     (`coverage_summary` actionable is empty, the ledger has no requirements to
     seed from, and `meta` exists so the T-259 nothing-asked branch is not
     taken). The engine's own repair is `intake.ensure_request_clause`, reachable
     only from the finish gate of a *live* ticket (`operations.py` ~7911), and
     T-1964 is already DONE, so no CLI verb can seed it. Engine-level gap.
   - Honesty constraint: SRC-407/SRC-410 both demand a hunt run at the current
     epoch; neither was run, so neither may be dispositioned VERIFIED.

2. **SRC-167's proof module is absent from every commit.**
   `.saipen/evidence/operator-wait/focused-verify-final.json` records 178 tests
   across 10 modules (1 failure, unrelated: `test_protocol_registry` load budget
   47136 > 47104). One of those modules, `tools/test_next_action_grammar.py`,
   does not exist in the working tree and `git log --all` never carried it --
   the same ledger-loss shape T-2049 measured for the GC engine. The
   implementation itself is present (`tools/saipen_engine/` carries the `WAIT:`
   grammar and `WAIT_OPERATOR` in `continuation_assessment.py`), and
   `test_next_action_deadlock` 8/8, `test_refusal_registry` 6/6,
   `test_user_wait_release` 4/4 pass in the current tree, but the audit's
   red/green controls (R005) cannot be re-derived from committed bytes.

3. **DONE lines recorded against red gates (2, adjacent to item 1).**
   T-1606's own verify is "every actionable clause of SRC-167 is terminal with
   evidence" -- all nine are UNKNOWN. T-1961's own verify is
   "validate_future_gate reports no error for a slice ticket whose DONE row was
   pruned" -- the validator still reports it (item 4). Neither line can be
   corrected without rewriting history, which is forbidden; the receipts name
   the work that must actually be done.

4. **FUTURE GATE FG-0046 names T-1936, which is not on BOARD (1).**
   T-1936 exists only inside the T-1961 row's prose. `saipen source recover`
   is the advertised repair for a moved row; it re-inserts a row only from an
   owned archive carrier, and no such carrier exists for T-1936.

5. **Closure provenance does not resolve (1).**
   `EX-000050` was verified against installed engine generation
   `sha256:c6819eff239d8b9c...`, the running engine is
   `sha256:bb180b28751da129...`; and T-2040 and T-2045 both name cohort
   `C-021`, which has no durable registry record. Measured:
   `.saipen/kitchen/cohort_registry.json` holds exactly C-001..C-020.
   `saipen cohort status C-021` -> `VALIDATION_FAILED`, "cohort C-021 has no
   durable registry record -- BOARD prose is not cohort authority".
   `cohort_reconcile` cannot create the record: `plan()` does
   `cohorts[target_id]` and refuses on absent. The record is only written by
   the release path (`release.py:_cohort_registry_target`).

6. **Runtime manifest names files git does not track (17).**
   `tools/_t2040_experiment.py`, `tools/saipen_engine/gc.py`,
   `tools/saipen_engine/source_reindex.py`,
   `tools/test_nested_git_boundaries.py`, eleven `tools/test_t2040_*.py`,
   `tools/test_t2050_pruned_row_restore.py`,
   `tools/test_t2051_source_reindex.py`. The manifest is
   `saipen/MANIFEST.json`; `tools/` is a `copy_trees` member, so there is no
   entry to drop -- the only repair is a commit. Measured route status:
   - `saipen ship` (dry run) -> `CREW_NOT_READY`, "crew not ready to ship:
     active Core ticket prevents terminal ship" (STATE.task = T-1449).
   - `saipen ship --isolated` -> the CLI rejects the flag outright
     (`ship accepts no arguments; surplus: --isolated`).
   - HEAD and origin/main are diverged: 9 commits on HEAD not on origin/main,
     5 on origin/main not on HEAD (`git merge-base --is-ancestor` fails), the
     `NON_FAST_FORWARD` refusal E-20593 recorded for the same reason still
     holds. Publication needs an operator lineage decision.
   Note the engine's own guard: committing these alone is refused by design
   (`_uncommitted_symbols` warns "do NOT commit it alone; it will fail in every
   clone" for 14 of the 17, because their subject modules are themselves
   uncommitted), so the 17 files are one commit set, not 17.

7. **Translation README badge drift (32).**
   All 32 locale READMEs still carry an old badge; expected `**v8.1.0**`
   (VERSION is `8.1.0`). The files live under
   `.saipen/saitranslate/kitchen/<locale>/README_XX.md`, i.e. protocol-owned
   producer output; the version-parity writer is the release path
   (`release.py:_check_parity`), not a hand edit.

8. **Unrouted by the validator, still real.**
   `saipen audit ingest` -> `SOURCE_UNRESOLVED`, "linked Work T-2016 is not
   DONE", receipt SRC-386, so the audit-inbox route stays closed; LOG is past
   its soft cap (1671 lines / 524 KB) and awaits `saipen transition CLEAN`.

## What is executable without a human

None of items 1-8 is closable by a source edit that does not falsify history:
each repair is either (a) a producer/release run (`cohort`, `saitranslate`
badge parity, the hunt SRC-407/SRC-410 demand), (b) a commit whose path is
gated on a crew that cannot ship while any Core ticket is active, or (c) a
disposition whose evidence does not exist yet. Verified green in the current
tree and recorded above: `test_next_action_deadlock` 8/8,
`test_refusal_registry` 6/6, `test_user_wait_release` 4/4, the T-2051 focused
unit 10/10 (E-20990).