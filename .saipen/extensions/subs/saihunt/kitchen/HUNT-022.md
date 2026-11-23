# HUNT-022 -- bounded six-signal sweep at dc39709c / tree 1a368781

- source_head: dc39709c0c17a3272126c01a626ffcaa4176140b
- source_tree_fingerprint: git-delta-v1:1a368781b8bbe259b5218e35666c2732b2531304247854b750c561f1f888ada9
- role_revision: sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5
- epoch context: converge_intent-f74cb6f3247c405fbf754e4a71a9eee5 (T-2070/T-2071/T-2072 deferred; union payload 7 paths)
- mode: read-only toward the main tree; every write below is inside this role's kitchen

## What changed since HUNT-021

HUNT-021 was bound to tree c9c3e86c. The tree now reads 1a368781 because the epoch payload
(tools/saipen_engine/audit_route.py, board_scrub.py, future_gate.py,
operations.py and their three test modules) is in the worktree as tracked
modifications. HUNT-021 is therefore stale by source (PROTOCOL.md § 6 class 1), superseded
by this package, and no claim of HUNT-021 is inherited here.

## Signal 1 -- failing tests: REPRODUCED (both gates), all classes already owned

Installed canonical gate, `saipen validate --json` at this tree
(`_hunt022_installed_validate.json`): `CONFORMANCE_UNHEALTHY`, `conformance_status
CURRENT_FAIL`, 3 problems / 18 warnings, `structural_gate: pass`, install identity
`install-v1:fedda813…` MATCH running/persisted. The three problems:

1. `source_receipt_unresolved_work` -- DONE Work T-2072 has unresolved source receipt
   SRC-418. T-2072 is DONE in this epoch by crew-defer; the provenance chain is the
   deferred ticket's own, not a live defect. Owned by T-2072/T-2058.
2. audit route not followed -- the INSTALLED engine still applies the pre-T-2070 guard,
   so it routes `saipen audit ingest` for the T-2016 layer while `next_action` is
   `saipen crew`. The repo generation does not report this line. The fix is payload
   path tools/saipen_engine/audit_route.py, deferred under T-2070.
3. `FUTURE GATE: FG-0046 names slice ticket T-1936, which is not on BOARD` -- the
   installed engine cannot restore the gate-pinned DONE row. The repo generation does
   not report this line either. The fix is payload paths board_scrub.py/operations.py/
   future_gate.py, deferred under T-2071. Publication is blocked by the dirty surface
   (`SKIP: DIRTY_SOURCE`), owned by T-2058.

Repo-generation gate, `python -B tools/validate.py` (`_hunt022_repo_validate.txt`):
exit 1, **29 problems / 38 warnings**. Classes: 1 × SRC-418/T-2072; 27 ×
runtime-manifest names a file git does not track (tools/ engine modules and t2040/t205x
test files, including the payload's tools/test_t2071_gate_pinned_row.py); 1 × EX-000053
closure provenance (verified against engine d64ee12e…, running b63ae691…). The
repo generation reports **no** audit-route failure and **no** FUTURE GATE failure
(`FUTURE GATE` appears only in a PASS line: deferred-authority surface valid, 1
PROMOTED). The two installed-gate failures the payload repairs are measured as absent
from the repo generation that carries the payload -- the first byte-level demonstration
of the fix outside the focused tests.

Focused controls, `_hunt022_tests.txt`, 6 modules, **101 tests OK, 6/6 exit 0**:
test_audit_route 32, test_t2071_gate_pinned_row 8, test_t2052_pruned_slice_closure 4,
test_t1614_future_gate 48, test_t1430_crew_run_receipt 3, test_refusal_registry 6.

## Signal 2 -- commits unverified in LOG: REPRODUCED, already owned

`git log -12 --format=%H`, each hash tested against `.saipen/LOG.md` as a whole-token
hex prefix of length 7-12: **1 cited (dc39709c0), 11 uncited** (7857dbf21, 00f290d90,
66ef622a4, b152e6de2, 88dab8ae4, 983470bd3, bc752edfa, 326fcdddb, 08e84d137, d5eca177a,
7373fcb9b). HUNT-021 measured 6/12 cited at the same HEAD; the field moved because LOG
pruning removed older citation lines, not because the commits changed. This class is
already routed by HUNT-021 to existing Core ownership (T-1449 cc-all closure audit;
T-2057/T-2058 evidence carriers). No new ticket.

## Signal 3 -- stale TODO/FIXME/HACK: NOT_REPRODUCED as a defect (bounded census)

177 engine files scanned (`tools/saipen_engine/**/*.py` plus tools/saipen.py): 164 raw
marker lines, unchanged from HUNT-021. In the epoch payload: 46 raw lines
(operations.py 43, future_gate.py 2, audit_route.py 1). Raw marker counts are not
defects and were not individually reviewed for staleness; the previous sweep's limit
carries over verbatim.

## Signal 4 -- silent failures: NOT_REPRODUCED as a defect (bounded)

AST census over the same 177 files: **0 bare `except:` with a pass/continue-only body**;
16 `except Exception`/`BaseException` handlers with a pass/continue-only body
(e.g. campaign.py:901, :1651, :1660). Those 16 were not individually reviewed for
reachability or intent, so this is a bounded NOT_REPRODUCED, not a clean bill. The
changed payload functions were covered by the red-control tests that exercise the
refusal paths (unreadable ledger keeps future_gate rule 6 failing; an open link never
owns ingest).

## Signal 5 -- symmetry gaps: REPRODUCED AS FIXED in the payload

Both pairs now exist on both sides, measured by line:

- prune/restore symmetry: board_scrub.py `gated_tickets` def:128, `select` def:156,
  `"gate"` retention branch:182; operations.py `restore_board_rows` def:27025,
  `gated_missing` check:27065-27066, `gated_tickets` binding:27064.
- capture/delete symmetry in the audit route: audit_route.py `linked_work_is_done`
  def:46, ingest guard:93, PHASE guard:97.

The asymmetry that T-2070 and T-2071 targeted no longer exists in the worktree source;
the installed engine still shows the pre-fix behavior until publication.

## Signal 6 -- dead code / orphans: NOT_REPRODUCED

Symbol reference census across `tools/**/*.py`: linked_work_is_done 2 files
(audit_route.py, test_audit_route.py); gated_tickets 3 (board_scrub.py, operations.py,
test_t2071_gate_pinned_row.py); restored_board_text 4 (board_scrub.py, operations.py,
test_t2050_pruned_row_restore.py, test_t2071_gate_pinned_row.py). No zero-reference
helper introduced by the payload. One manifest-class finding reproduce the repo gate
count already: tools/test_t2071_gate_pinned_row.py is named by saipen/MANIFEST.json and
untracked by git (tracked T-2058; one of the 27). No new ticket.

## BOARD ownership check

Every reproduced class maps to existing Core ownership: T-2070 and T-2071 (epoch
payload, fixes measured), T-2072 (DONE, SRC-418 provenance), T-2058
(PUBLICATION_STAGING_BLOCKED, 27 untracked manifest paths + dirty-surface injection),
T-1449 (commit/LOG closure audit), EX-000053/T-2052 (closure provenance). No untracked
defect was found; payload is empty by design.

## Limits

- Installed gate read through the installed validator, not re-implemented.
- Signal 2 citation method is a token-prefix match over LOG text, not a journal join.
- Signals 3 and 4 are raw censuses without individual staleness/reachability review.
- No main-project file was written, moved or deleted by this role.
