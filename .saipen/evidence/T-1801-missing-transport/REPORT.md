# T-1801 — settle a closed audit capture whose transport vanished

The public audit ingest path previously reported an empty inbox after an
external process removed a captured file, although its Source was CLOSED and
its binding remained ACTIVE. The shared retention provider kept its DONE Work
forever. T-1752 REVIEW measured this separately and opened T-1801; this Work
does not alter the original T-1752 completion.

## Implementation and owned scope

Owned product delta is limited to three parts of
`tools/saipen_engine/audit_inbox.py`: classification of a proven absent capture
with an intact CLOSED/retired Source into the existing CLOSED_PENDING_DELETE
route; accurate absent-transport projection text; and an empty-path journal
precondition for metadata-only settlement. The last condition refuses
STALE_STATE if a file appears between the absence proof and APPLY. It neither
deletes that new file nor releases its binding.

Existing consume/journal and ingest cleanup-before-capture remain the owners.
No new state, command, consumer, ledger or Work close bypass was added. Missing
ACTIVE Sources remain diagnostic orphans. Changed surviving generations and
uncaptured residue are retained. `delete_gate`'s preexisting absence semantics
are unchanged.

The preimage `before/audit_inbox.py` preserves all preexisting edits in this
shared file. The second owned path is
`tools/test_t1801_missing_audit_settlement.py`. Its eight public-path controls
cover missing file and missing directory, readonly projection, journaled
reference release, cleanup before new capture, repeated-ingest byte no-op,
ACTIVE Source retention, changed generation/residue, and reappearance refusal.
The new module has only an intent-to-add index entry; `index-intent.json`
records that 5,213 other index entries and the product bytes were unchanged.

## Executed evidence

Frozen native contract: `regression.json`. Native receipt:
`.saipen/evidence/regression/regression-execution-581eab5798d74385b360b33a1c3c7f4b.json`.
Same verifier cc009dba400d60f0044a91d81f393ee854ee3cc8e3faebc052c8d380c32973b3:
8 tests, pre-fix 6 failures; post-fix 0 failures, no skips. The native owner
recorded the pair in the active VERIFY cycle (E-15949/E-15950).

Focused and neighboring controls passed: 110 tests before the final eighth
case was added (2 environment skips), then 29 including the final eight and
whole-source refusal/command reachability/UTF-8 guards. Ruff 0.16.0 over tools/
and tests/ and whitespace passed.

T-1695's unchanged focused contract was re-executed at RV-000058: 38/0,
focused CURRENT_PASS. Its strict capture temporarily carried one finding;
the subsequent canonical `saipen validate --json` returned VALID/CURRENT_PASS,
0 problems and 9 existing warnings. No warning-free claim is made.

## Family and independent review

The original family (session 14999, PID 31864, started 17:49:56Z) completed
PASS: 6,676 discovered and run, zero red/new red, no problems or leaked
sandboxes. Typed record:
`.saipen/evidence/core-unit/54ca6c4a8207d8cd-20261015T181538Z.json`.
Its exact current product fingerprint is
54ca6c4a8207d8cdaa70ab546e4441fb2a3c00140614248fbcb91b327122734d.
`running-job.json` records the terminal family; never restart it.

VERIFY checkpoint E-15956 and REVIEW transition E-15957 consumed the current
evidence. REVIEW independently executed all eight cases again: PASS, 8/0,
preserved in `independent-review.txt`. `owned.patch` was reviewed against the
actual preimage, preserving other owners' hunks. No P0/P1 was found; memory
promotion NO (ordinary local invariant, no nonduplicate reusable decision).
The security/performance extension files are source-home example templates;
they declare no additional project scanner or benchmark.

E-15959 records SHIP, E-15960 enters it, E-15961 binds exactly the two owned
paths and E-15962 records skipped publication under standing no-publish policy.
Final canonical validation returned VALID/CURRENT_PASS, 0 problems and 9
warnings (`ship-validation.json`). Atomic own_patch finish
finish-88c294d5823b42c2a76e65d8dae5b867 recorded T-1801 DONE at E-15963 and
routed to T-1765. No commit, tag or push was performed or authorized.

Graph project/coverage tooling returned Transport closed. Exact named source,
the shared retention provider and canonical fixture were read directly; this
report makes no graph completeness claim.

## Approved next repair

The actual user compatibility choice for T-1765 was captured as SRC-260 at
E-15951 and projected at E-15953, creating append Work T-1802. Canonical
unblock E-15954 lifted T-1765's WAIT_USER_DECISION. Adopt ruleset 2, preserve
older baselines and measure new ones when needed. An isolated candidate and
11-case oracle are ready under `.saipen/evidence/T-1765-approved/`; the live
findings.py remains unchanged. This choice grants no publication authority.
The full cc all goal is still active.
