# T-1361 remeasurement 2026-09-21 (carrier isolation in place)

Command: `python tools/run_scenarios.py` from the repository root, host-session
carriers stripped, full output retained in run-console.txt.
Result: exit 1; elapsed 1069 s; 88 FAILED identities; 1330 PASS lines
(previous capture on ec53042a: 115 FAILED, 41 PROJECT_LINEAGE_MISMATCH).

## Root-cause partition v1 (by unique FAILED identity)

1. HOME-root validator cascade (~18-25 identities)
   Identities shaped `declared 'pass', got 'fail' (validator exit 1) | first
   FAIL: FAIL: cross-doc drift [root-file-set] ...` (block-park-done-green,
   blocked-ticket, cold-handoff-continuity, goal-counter-*, hr-claim-foreign-doing,
   invalid-mode-phase-combination, multi-agent-claim-conflict, proposal-mode-halt,
   release executor 11c/14, ...). The check reads the VALIDATOR's own checkout
   root, so every fixture that validates the SAIPEN home inherits the home's
   untracked-file state.
   Action taken this session: the three untracked root SAIHANDOFF reports were
   preserved byte-identically under evidence/T-1440-incoming-root-handoffs-20260921
   (README.md records provenance and why). The root-file-set line is gone from
   the home gate; the same fixtures now inherit the remaining untracked-file
   packaging class (`runtime manifest names a file git does not track` for the
   uncommitted T-1435/T-1437/T-1438/T-1439/T-1444 files), which is the
   DIRTY_SOURCE condition itself. A coherent commit identity is required before
   these can go green; no commit is authorized in this corridor.
2. release-executor 11c/14/15 (~8 identities): clone/commit-dependent checks
   (`fresh clone lacks the reviewed deletion`, `closure B is a child of the
   content commit`, `untracked-only release returns RELEASED` -> RELEASE_FAILED
   with the same root-file-set first FAIL). Same DIRTY_SOURCE dependency.
3. subprocess exits (12 identities): `exit 1, expected 0` families (advanced LOG
   marker, correct/explicit/nested root, recovered tail, legacy absence warns,
   marker repairable drift, gate-closure red control, continuity probes
   ATTEMPT_ACTIVE). Each needs its own reproduction; several are root/lineage
   fixtures whose validator call also reads the home.
4. missing-expectation (7 identities): `missing 'Agent is conformant'`,
   `missing output 'Project root: ... (git-worktree|git-common|explicit)'`.
5. continuity/attempt (1): `while an episode is live refuses deterministically`
   returned ok ATTEMPT_ACTIVE idempotent instead of the expected refusal shape.
6. other (50 identities): not yet clustered; full identity list is in
   run-console.txt (grep `^FAILED:`).

## Next exact action

Cluster partition item 6 (the 50 unclustered identities) from run-console.txt
by first-FAIL line and subprocess exit code, then repair one root cause per
owner. Before the HOME-root cascade (items 1-2) can be green, a coherent commit
identity must exist for the accumulated protocol work; that decision belongs to
the operator (no commit/push/tag in this corridor).
