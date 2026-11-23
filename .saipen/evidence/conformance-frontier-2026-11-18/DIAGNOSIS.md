# Conformance frontier — measured 2026-11-18 (night shift 3 continuation)

Question: after T-2089 (E-21695), what still separates the project from
CONFORMANCE_CURRENT_PASS, and which of those findings are repairable from
this seat without operator authority?

## Installed-engine conformance verdict (the canonical authority)

`saipen validate` binds `C:/Users/vac34/AppData/Local/saipen/scheduled-source`
(8.1.0). After this shift's two permitted repairs, verdict: CURRENT_FAIL
with exactly 3 blocking findings:

1. **Audit route** (`unclassified`, finding 76b48f23558dce11): inbox routes
   `saipen audit ingest` for `SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md`;
   `saipen audit ingest` refuses SOURCE_UNRESOLVED (SRC-386 linked Work
   T-2016 is not DONE). Rule defect, repaired in the 8.1.1 worktree by
   `tools/saipen_engine/audit_route.py` (route owns continuation only when
   its linked Work is DONE) — E-21439 measured route_violation=None on the
   fixed generation while the ordered route is unfollowable.
2. **FG-0046 / T-1936** (`unclassified`, same finding key): future gate names
   a slice ticket a canonical board_scrub pruned (DONE E-18545). Rule defect,
   repaired in the 8.1.1 worktree (ledger-closed slice acceptance,
   `tools/saipen_engine/future_gate.py`) — E-21439 measured 0 errors on the
   fixed generation.
3. **Coverage gap** (`coverage_gap`, e54399132c79dc9d): shipped test-fixture
   doc `tools/regression_t2089/home_extensions/subs/PROTOCOL.md` classified
   by no validator pattern. New this shift: repaired in the worktree
   `tools/validate.py` with an EXEMPT row for `tools/regression_*/**/*.md`
   (test-fixture prose copied into throwaway sandboxes by regression oracles,
   not a shipped protocol doc). The installed validator (8.1.0) lacks the row
   and will keep reporting the finding until the runtime generation moves.

## Why the worktree cannot cure the installed verdict

Measured directly this shift: the repo validator `tools/validate.py
--no-receipt` passes doc coverage ("490 shipped documents, 29 checked, 39
exempt") and shows none of the three findings above. The conformance
authority, however, resolves through the installed generation, whose
`tools/validate.py` (9466 = same rule, no new EXEMPT row) still fails it.
Committing the worktree and moving the installed runtime are the publication
cycle owned by T-2058 (`.saipen/evidence/T-2058-release-index/BLOCKED.md`):
gate A (EX-000053 generation binding refuses the repo pre-commit) and gate B
(CREW_NOT_READY, SC-7 with excluded closure tickets). Both demand an
operator decision already recorded there; this seat cannot mint it.

## Repo validator baseline after this shift's repairs

`python tools/validate.py --no-receipt`: 38 problems, 40 warnings. All 38
FAIL lines are the two carried classes:

- 37× `runtime manifest names a file git does not track` — every untracked
  `tools/` member of the `tools` copy-tree in `saipen/MANIFEST.json`
  (previous shifts' test files and engine modules, measured: 0 of 38 in the
  explicit files list, all from the copy-tree expansion). Repair is
  `git commit`, which is the publication cycle.
- 1× `history: 125 sealed LOG entries predate the mandatory DATE` — the
  permanent sealed-history warning-owner class (T-1119 family), immutable by
  append-only design.

No new red class was introduced: the closure-evidence finding on T-2047 was
cleared by `saipen work reverify T-2047 --run "python -m unittest
tools.test_t1430_crew_run_receipt -v"` (RV-000093, verdict
PASS_WITH_CARRIED_DEBT, executed exit 0, 5 tests OK). An earlier reverify
(RV-000092) honestly recorded FAIL because its run-chain included the
whole-tree validator; superseded by RV-000093.

## Repairs executed this shift (repo worktree only)

- `tools/validate.py`: EXEMPT row `tools/regression_*/**/*.md` with reason.
- `saipen work reverify T-2047` ×2 (RV-000092 FAIL recorded, RV-000093 PASS).

No canonical BOARD/LOG/STATE mutation was attempted; T-2058 stays BLOCKED and
the three installed findings stay honestly open on the installed generation.
