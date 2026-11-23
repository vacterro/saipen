# Conformance delivery packet, measured 2026-11-16

Live state: HEAD dc39709c0, tree git-delta-v1:f3dab073, STATE DONE / next_action
"saipen crew" / E-21418. `saipen continue` refuses CONFORMANCE_UNHEALTHY:
CURRENT_FAIL, 2 problems, 16 warnings, receipt-8b3e1d6a8320, gate core,
validator install-v1:c8b61d5b (VERSION 8.1.0).

## The two problems are exactly two source patches

Same live BOARD/inbox data, two engine generations, measured in one probe:

| check | installed 8.1.0 | source 8.1.1 |
| --- | --- | --- |
| `audit_route.route_violation(projection, "saipen crew")` | `the audit inbox routes 'saipen audit ingest' (layer None, audit/SAIHANDOFF_BZ_REA_AGENT_DRIFT_RECOVERY.md) ...` | `NONE` |
| `future_gate.validate_future_gate(root, tickets)` slice errors | 1: `future gate FG-0046 names slice ticket T-1936, which is not on BOARD` | 0 |

Repair pair, both already in current-head release scope and byte-current:

- `tools/saipen_engine/audit_route.py` (T-2070, scope-450a898c: sha256 a934c36b)
  -- `audit_route_owns` refuses to own a `saipen audit ingest` whose linked Work
  is not DONE, so T-2016/SRC-386 (BLOCKED_EXTERNAL, foreign half) stops being
  routed to a command its own executor refuses.
- `tools/saipen_engine/future_gate.py` (T-2072, scope-8e43c95e: sha256 40e698a7)
  -- an absent slice ticket is answered against the LOG ledger once
  (`board_scrub.closed_in_history`), so FG-0046/T-1936 (closed at E-18545, row
  pruned 2026-10-30) stops reporting a broken link.

Focused proof on these bytes now: `python -m unittest tools.test_t2071_gate_pinned_row
tools.test_t2052_pruned_slice_closure tools.test_audit_route` -> Ran 44 tests, OK,
exit 0.

No data write repairs either finding: T-1936's row is restorable only by
`source recover --confirm` (T-2050/T-2071, absent from 8.1.0; the installed verb
rejects arguments), and the installed router cannot stop owning the ingest.
Trying the source generation is refused by the home guard: HOME_REQUIRED
"home-divergent" -- only the persisted install may mutate.

## What blocks delivery today

The sanctioned channel is the `saipen-inject` task from committed HEAD
(bootstrap/schedule-run.ps1: clean injected surface -> one HEAD snapshot ->
scheduled-source + machine runtime). Its own log at 00:01:02 today:
`SKIP: DIRTY_SOURCE` (rc=2); next fire 00:16.

Injected surface = 58 MANIFEST paths. Dirty now: 65.

| class | paths | state |
| --- | --- | --- |
| current-head release scope (dc39709c) | 12 | T-2055 3, T-2070+T-2072 2, T-2071 3, T-2072 2, T-2047 2 -- all byte-current except one T-2055 REPORT.md |
| historical scope only | 38 | older heads; not bound to what would be committed |
| never scoped | 27 | T-2040 subset (incomplete, non-importing), T-2049 gc.py (BLOCKED), T-2050/T-2051/T-2056 (rows absent), T-2057/T-2059/T-1880 (BLOCKED), release_ledger_baseline, conformance test files |

So the surface cannot be made clean by committing what is verified alone: 53 of
65 paths are not attributable at HEAD, and committing them would publish
incomplete or blocked work. Parking the remainder byte-exactly is the routine
used at 7857dbf2 on 2026-11-13 (operator OPTION A, README at
.saipen/evidence/T-2052/publication-parking/README.md), and it is a staging
decision this shift's handoff explicitly does not grant.

## The one decision

OPTION A -- authorize the narrow delivery: park the 53 unattributable surface
paths byte-exactly (stash by explicit pathspec + independent sha256 copy),
commit the 7 current-head scoped paths of T-2070/T-2071/T-2072, let
`saipen-inject` publish, restore the parked bytes, verify 29/35-style byte
identity. Expected: conformance 2 problems -> 0, `saipen continue` routes again;
installed home gets the fixed engine; rollback = scheduled-source-previous.

OPTION B -- stop. Conformance stays red; `continue` stays refused; BOARD has 0
DOING and 1 TODO (T-2062, needs T-2059 -> T-2061 -> native ZAICODE operator
carrier). Nothing else is claimable; this is a terminal wait, not a queue.

Not bundled here and unchanged: the 618-deletion intake wave and archive
publication (T-2058), and origin/main 60783ac4 not being an ancestor of HEAD --
both remain separate operator decisions, already measured in
.saipen/evidence/T-2058-staging-premise-remeasured.md.

Honest limit: the injector does not run the core-unit family gate; that gate
stays red on the pre-existing T-1449 classes. OPTION A's proof is the focused
set (44 tests here, 50 in E-21252), not a family PASS.

## Measured prediction of OPTION A's delivery state (2026-11-17, read-only)

Candidate generation assembled in the temp dir (NOT installed, NOT published):
installed 8.1.0 `tools/` + `saipen/` + `extensions/` verbatim, with exactly the
two fixed modules swapped in (`saipen_engine/audit_route.py` sha256 a934c36b...,
`saipen_engine/future_gate.py` sha256 40e698a7...). Same project data, same
probe script as the two-generation measurement above:

    ENGINE V:\_TEMP_\saipen_cand\tools\saipen_engine
    PROJECTION {"action": "saipen audit ingest", ..., "work": "T-2016"}
    ROUTE_VIOLATION NONE
    FUTURE_SLICE_ERRORS 0 []

i.e. both blocking findings present in installed 8.1.0 vanish when only the two
delivered modules change -- the projection still names the ingest, but the fixed
router stops owning it (the executor's own SOURCE_UNRESOLVED refusal is then the
answer, which is legal), and the pruned T-1936 slice resolves as closed in
history.

This is a PREDICTION of the post-delivery state, not a gate verdict: the
candidate home is a copy, its engine sha256 differs from the installed
fingerprint, and the validator run against it fails two candidate-completeness
artifacts (missing bootstrap/, engine sha mismatch with DONE provenance
EX-000053) that do not exist in the real home. Per the handoff's STOP condition,
a green asserted by a different engine does not count; only the installed
home's own `validate.py` after a real publication can.
