# T-1972 -- staging decision for the release-metadata slice

## What the gate demanded

`tools/validate.py --gate ship` sets `require_release_index = True` for every
ship gate (`validate.py:487-490`), so a binding ship-gate run always requires
the whole `release_contract.release_metadata_paths` slice to be represented in
the index. Measured slice: **4,242 paths** (2,156 below `.saipen/intake`,
2,078 below `.saipen/archive/source`, 7 root metadata files, 1 other).

The gate's own four sets, recomputed with its batching semantics
(`_git_pathspec_sets`, `_PATHSPEC_BATCH = 100`):

| quantity | count |
|---|---|
| slice paths | 4,242 |
| tracked in slice | 3,479 |
| unstaged (diff) | 623 |
| need_staging | 1,386 |
| -- absent from worktree (deletions) | 618 |
| -- present but untracked | 768 |
| staged in index before this ticket | 0 |

## The decision

Stage all 1,386 `need_staging` paths, explicitly enumerated, no `.` and no
`-A` (ship.md 6b.4). The three classes and how each was adjudicated:

1. **618 intake deletions.** Every one has an archive counterpart under the
   four documented naming maps (`contracts/SRC-NNN.json` ->
   `SRC-NNN.contract.json`, `contracts/SRC-NNN.rNNN.json` unchanged name,
   `coverage/SRC-NNN.json` -> `SRC-NNN.coverage.json`, `active/*` unchanged
   name). Measured: **0 of 618 lack an archive counterpart.** No release data
   is at risk.

2. **636 untracked archive carriers** (101 distinct receipt ids). Every id
   resolves to a tombstone in `.saipen/intake/index.json`; **0** are neither
   tombstoned nor active, and **0** are still active. These are canonical
   close/archive output, not stray copies.

3. **5 modified canonical state files** -- `intake/index.json`,
   `intake/audit_allocator.journal`, `intake/audit_inbox.json`,
   `coverage/SRC-290.json`, `coverage/SRC-342.json`. These carry the
   migration's own settled receipts.

Not staged, deliberately: the 5 files already in the index from earlier work
(`extensions/adapters/zaicode/saipen-guard.py`,
`tools/saipen_engine/operator_origin.py`, `tools/test_t1859_zaicode_seal.py`,
`tools/test_t1966_broker_liveness.py`,
`tools/test_t1966_chain_truncation.py`). ship.md 6b.3 requires preserving user
staging; they are outside the slice and were left byte-identical.

## Proof

- Pre-ship index tree backed up: `86b0736715f4c4ec40649539ea9e84a6823fefc0`
  (`pre-ship-index-tree.txt`), HEAD `66ef622a…` (`pre-ship-head.txt`).
- After staging, every one of the 1,386 requested paths is represented in the
  staged diff (renames verified on both sides via `--name-status -z`), and 0 of
  the 618 worktree-absent paths still carry an index entry.
- `ship-gate-post-staging.log`: **52 PASS, 4 FAIL**. The two failures this
  ticket owned are gone -- `release index is empty` count **0**,
  `staged release metadata differs from working-tree bytes` count **0** --
  and `git diff --name-only` across the slice returns **0** paths.

## What this ticket does NOT fix

The 4 remaining ship-gate failures are other owners':

- SRC-037 corrupt archive coverage -> **T-1971**
- EX-000029 closure provenance (engine generation moved) -> release/closure
  owner
- stray root file `SAIPENFUTURE_CONTEXT_GRAPH_20260909_1811.md`, twice
  (root-file-set and coverage-gap) -> **T-1971**

## Operational note

`git add` with 1,386 long pathspecs crashed git's Windows fscache
(`compat/win32/fscache.c:133`, `Trying to allocate fsentry for long path`)
and left a zero-byte `.git/index.lock`. The lock was removed only after
`Get-CimInstance` proved the five running `git.exe` processes were all
`fsmonitor--daemon run --detach`, i.e. no in-flight index writer owned it.
Staging then succeeded with `-c core.fsmonitor=false`.

## Coupling disclosure

This decision pins the SRC-037 coverage file's **corrupt** bytes
(`6eacdf24…`) into the index, because it is one of the 1,386 paths the gate
demands. That is a consequence of the gate's whole-slice rule, not an
endorsement of those bytes. T-1971 must resolve the bundle before any commit
lands; committing this index as-is would make the corruption permanent.
