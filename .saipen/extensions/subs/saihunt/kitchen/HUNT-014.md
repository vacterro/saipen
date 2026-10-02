# HUNT-014 — bounded continuation audit

Source: b7f5b51280b8f49c5fedbf7a00aeb6d4f45743ba
Tree: git-delta-v1:4c6fd9b3f13a1d7a0b203e00a759dae5eac1474eabb77cb3e39dad9da1953eb9
Date: 2026-09-20

Scope: current closure routing, conformance receipt classification, crew receipt
command reachability, and the adjacent intent tests. This is a bounded sensor
pass, not full-suite or repository-wide correctness evidence.

1. Failing tests — REPRODUCED. `python -m unittest
   tools.test_router_closure_readiness tools.test_intent_audit_fixes` ran 47
   tests in 16.374s, with four failing subcases in three intent test methods.
   All six closure-readiness tests passed. The failing intent fixtures stop at
   RECONCILE_REAUTH_REQUIRED for legacy T-001 without execution evidence.
   Existing T-1346 owns these four failures; do not duplicate its ticket.
2. Unverified commits — NOT_REPRODUCED within the current HEAD boundary.
   Core LOG E-7537 names b7f5b512 with the six-test closure evidence and adjacent
   regression results. This run independently reran the six-test suite.
3. Stale TODO/FIXME/HACK — NOT_REPRODUCED in closure_readiness.py, router.py,
   and conformance.py. The matches in router.py are descriptions of the BOARD
   TODO section, not deferred implementation markers.
4. Silent failures — the HUNT-013 malformed receipt-timestamp claim is NOT
   established on current code. conformance.py:1119 validates the timestamp;
   conformance_status calls that strict decoder at line 1203 before age
   classification. The later catch at line 1258 alone does not prove the
   asserted behavior. No bypass experiment was performed; the old claim must
   not be collected as a reproduced defect on that isolated expression.
5. Symmetry/reachability — REPRODUCED by static caller census. Production
   Python source under tools contains definitions of record_crew_run
   (operations.py:8532) and record_producer_integration (operations.py:8660),
   but no callers; tools/saipen.py exposes neither writer. The live crew
   carrier requires a committed crew_run receipt for SC-2. The journaled
   Python API exists; the missing surface is the CLI route. Core must not
   pretend a READY OUTBOX alone is epoch execution evidence.
6. Dead/orphan code — no separate new finding in the changed closure module:
   its public decision has real consumers in router.py:724 and
   operations.py:3038. The two uncalled receipt writers belong to signal 5,
   not a second finding or an authorization to delete them.

Graph limitation: project saipen, generation 2026-09-01T13:16:39Z, explicitly
excludes tools/. Coverage was checked and evidence above was read directly
from current source. No exhaustive graph-based absence claim is made.

Main source was not edited. Existing dirty files were retained. The old
HUNT-013 package is preserved and marked stale because its source identity
does not match this run.
