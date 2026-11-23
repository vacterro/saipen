# T-2052 publication settlement — owner-coordinated parking

Operator authorization: OPTION A (coordinate legitimate owner-controlled commit
or safe parking of the conflicting changes). No foreign work was committed,
discarded or force-stashed; nothing was reinterpreted in policy.

## Why parking and not committing

The 35 dirty injected-surface paths are not one change set. Attribution read
from the live bytes (not from a report):

| Change set | Paths | State |
| --- | --- | --- |
| T-2040 residual (nested-Git boundaries, retry-proof refusals) | `tools/freshness.py`, `tools/saipen_engine/conformance.py`, `tools/saipen_engine/router.py`, `tools/test_nested_git_boundaries.py`, 11 x `tools/test_t2040_*`, `tools/_t2040_experiment.py` | INCOMPLETE |
| T-2050 (pruned closed row restore) | `board_scrub.py`, `intake.py` (+`operations.restore_board_rows`), `remediation.py`, `test_t2050_*` | implemented, tests green |
| T-2051 (source index re-derivation) | `source_reindex.py`, `operations.reconcile_source_index`, `test_t2051_*` | implemented, tests green |
| T-2049 (provenance-safe GC) | `tools/saipen_engine/gc.py`, `GC_*` error codes in `saipen/REGISTRY.json` | untracked module only |
| fixture/CLI repairs | 4 x `_seat_state` execution-intent fix, `test_t1949_hook_validator_status.py`, `tools/saipen.py` source verbs, `saipen/COMMANDS_REFERENCE.md`, `tools/core_unit_baseline.json` | mixed |

The T-2040 subset is proven incomplete, so it cannot be committed as verified
work: 10 of its 12 new test files raise
`ModuleNotFoundError: test_t2023_goal_management_and_maintenance_binding`, and
the remaining two (`test_t2040_terminal_consumer_*`) import
`checked_discovery_evidence` and `saipen_engine.outcome_truth`, neither of
which exists in the tree. Those modules live only in the older `t2040-wip`
stash, i.e. the worktree holds a partial restore of a larger parked body.

Committing the whole surface would have published unreviewed, non-importing
work to every installed home. Parking preserves it byte-exactly instead.

## What was done

1. `inventory-before.txt` — the exact `git status --porcelain=v1 -uall`
   output for the MANIFEST-declared injected surface: 18 modified + 17
   untracked = 35 paths.
2. `sha256-before.json`, `tracked.patch`, `untracked/` — a second, independent
   copy of every parked byte (patch for tracked, verbatim files for untracked).
3. `git stash push -u -m "t2052-publication-parking 20261113T1510Z ..." --
   <the 35 paths>` — scoped by pathspec only; no `git add -A`, no
   `reset --hard`, no `clean`, no global `stash -u`. Result: `stash@{0}`.
4. Surface re-read with the scheduler's own predicate: 0 dirty lines.
5. `schtasks /run /tn saipen-inject` — the sanctioned scheduled publication.
   `%LOCALAPPDATA%/saipen/inject.log`, run `e5408c58e98d40ac8f7a8a0eadba1af3`:
   `clean: injected surface matches HEAD (58 path(s))`,
   `source: HEAD 7857dbf21567bc387d14b556d3826eeb544ed2a6`,
   `convergence: head=7857dbf2 publication=CURRENT convergence=CURRENT pending=0`,
   `stamp: machine runtime refreshed: MACHINE_RUNTIME_INSTALLED`, `end rc=0`.
6. `git stash apply stash@{0}` and byte verification: 29/35 identical raw,
   6/35 identical after LF/CRLF normalisation (the six files git had warned
   about on the way in). Content restored exactly.

## Publication verification

- `scheduled-source/tools/saipen_engine/convergence.py` LF-normalised SHA-256
  `de2b20477727fd54b0d57c62949e4304974ae1a2775fa61f1a01054f3da9ea0b` — identical
  to `git show HEAD:tools/saipen_engine/convergence.py`.
- Machine runtime generation `gen-sha256:66020545630bea30…` (PATH launcher
  target, installed 2026-11-13T13:11:00Z) carries the same bytes; generation
  `495850fb3c29f94c` is retained as `previous` (rollback) and is pre-fix by
  design.
- HOVERSTRATA against installed bytes: stages `E F G H I`, latest I
  `2026-11-13T11:45:14Z`, `convergence.ok True`, external oracle 3/3 OK,
  closure gate `C3 True C4 True` (C7 False — T-7 itself is still open).

## Outcome

- `hoverstrata-status-installed.json` — HOVERSTRATA `saipen status --json` on the
  published runtime: `convergence_current: true`, `closure_complete: false`
  (C7 false: T-7 was still the open row).
- `hoverstrata-gate-installed.json` — closure gate on installed bytes:
  `C1..C8` = `true,true,true,true,true,true,false,true`; stages `E F G H I`;
  latest I `2026-11-13T11:45:14Z`.
- HOVERSTRATA T-7 settled through its own gates (SCOUT..SHIP, finished).
- `hoverstrata-status-post-done.json` — after T-7 closed: `disposition COMPLETE`,
  `reason_code closure-complete`, `convergence_current: true`,
  `closure_complete: true`, `completed_at 2026-11-13T11:45:14Z`. That is the
  acceptance T-7 asked for, measured on installed bytes with the original E-I
  receipts untouched.

## T-2052 itself

Verified and published, but not closable: the SHIP gate requires a full
`unittest discover -s tools -p test_*.py` run cited in the current VERIFY cycle
and judged against `tools/core_unit_baseline.json`. That family is red for the
classes already measured under T-1449 (E-21001, E-21004), 12 of them untracked
`tools/test_t2040_*` that cannot import. Re-running the unchanged family is
forbidden by PHASE-DELTA-01, so T-2052 carries a `SHIP_EVIDENCE_PREREQUISITE`
blocker with that exact ownership instead of a laundered closure.

## Recovery

The parked bytes exist in three places: `stash@{0}` of this repository, the
`tracked.patch` + `untracked/` copies here, and the worktree itself (restored).

- Re-apply if the entry was dropped: `git stash apply stash@{0}`
- Or from this directory: `git apply --3way tracked.patch`, then copy
  `untracked/` back over the tree.
- The T-2040 subset additionally needs `t2040-wip` (`stash@{1}`) for the
  modules its tests import; that is its owner's decision, not this ticket's.
