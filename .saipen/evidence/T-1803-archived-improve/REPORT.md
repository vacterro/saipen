# T-1803 / SRC-261 — archived Improve reconciliation

## STATUS

VERIFY COMPLETE (PASS); entering independent REVIEW and local no-publish SHIP.
The expanded 36-control native before/after execution passes (E-16213 FAIL /
E-16214 PASS), the full declared unit family passes (6792 ran, 0 red, 0 new red
at E-16215), and strict-core conformance passes (receipt-db85d1fb8ab3). Neither
AUDAPACK T-311 nor the broad cc all] objective is claimed complete.

The inherited report claimed completion, another HEAD/version, nonexistent
symbols and incorrect historical counts. Its exact bytes are preserved in
REPORT-inherited-unverified.md. This report supersedes those claims with
current source and measured evidence.

## AUTHORITY

Engine root: V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN.
HEAD: 025bf596c683464788ab698248e8a3c5eb44dfec. VERSION: 8.1.0.
Work: T-1803; owner saipen-cli; Source SRC-261, 33 actionable clauses.
Source provenance is model_supplied, never represented as operator_carrier.
Canonical START/continue admit local engineering under the existing degraded
host policy (permitted true, verified false); this is not mechanical host
authentication. E-16190 records the original authority/boundary inspection.

continuation_authority: operator_required; authority_source: E-16134;
authority_until: budget; safety_valve_mode: hard_wait. These remain unchanged.
No operator capsule, publication approval or consumer mutation is inferred.
Initial native pair: E-16200 FAIL / E-16201 PASS (35 controls). Terminal native
pair after malformed-JSON input-shape repair: E-16213 FAIL / E-16214 PASS (36
controls). Terminal full family: E-16215 PASS (6792/0/0).

AUDAPACK remains read-only: lineage-79944d6c0334416ebe1001e97de6c1cc, E-3368,
T-311 BLOCKED. current-audit.json rechecks all 13 protected path entries from
baseline-observation.json, including two explicitly absent SWEEPs. Every
digest matches. Acceptance mutators target disposable copies only.

## ROOT CAUSE

The actual owner is tools/improve.py; tools/saipen_engine/improve.py is absent.
The actual abort symbol is abort_cycle. baseline-observation.json reproduces
both requested historical cases against preserved pre-fix bytes:

- reconcile_cycle classified committed content as STILL_ACTIONABLE, then
  returned ALREADY_TERMINAL solely because the manifest was archived.
- Ordinary write_sweep_entry, retire_seat, complete_report and abort_cycle
  correctly refused archive mutation. _require_cycle_amendable correctly
  required an existing disposition, leaving no legal first-disposition path.
- cycle_liveness inspected the primary seat, hid secondary findings and
  advertised impossible archived submit routes or empty drafts indefinitely.

Those ordinary archive refusals remain. The missing mechanism was a successor
outside immutable history. The initial full family additionally caught an
unregistered retrospective- writer class; journal.OP_CLASSES now registers it.
The two original failures are preserved and are not added to the baseline.

## ARCHITECTURAL FIX

The new improve_retrospective module stores append-only version-1 JSONL
successors at .saipen/improve-reconciliation/<cycle>.jsonl. Headers bind
lineage, exact cycle identity and SHA-256 of every original history file,
including missing SWEEP state. Events bind seat/report#RUN/IMP identity,
previous hashes, actors and native COMMITTED receipts for each byte prefix.
A digest grants no execution authority.

Existing sweep/retire verbs require explicit --retrospective. Resolved
dispositions require owned verification files bound by hash; ALREADY_FIXED
also requires fixed-by evidence. Archived drafts cannot mint CONFIRMED
authority. Existing final authority cannot be replaced. A pending
NEEDS_EXTERNAL_EVIDENCE disposition advances only by explicit append-only
amendment with proof; exact retries write nothing and conflicts refuse.

Admission, owned Work, lineage, WAIT/NO_GO and producer protections remain.
The canonical writer lock, target CAS and read dependencies bind original
history, checkpoint and proof files. A versioned improve_retrospective_v1
journal policy uses the same semantic validator for apply and recovery.
Old kernels refuse that policy. Untouched PREPARED transactions may abort;
verified materialized transactions roll forward or retain an explicit conflict.

All seats/findings are classified. Empty archives require no invented report
completion. Unadjudicated findings remain in sweep-queue. Missing external
evidence remains visibly blocked without repeated actionable advertisement.
Adjudicated archives use existing COMPLETE/SUPERSEDED/BLOCKED_EXTERNAL
outcomes and preserve the original cycle/report bytes and identities.

## EXACT CHANGED SYMBOLS

current-audit.json binds exact preimage/current hashes and AST symbol changes.
mission-only.diff isolates this mission from inherited dirty work.

| File | Actual changed symbols |
|---|---|
| tools/improve.py | _journaled_write, write_sweep_entry, retire_seat, reconcile_cycle |
| tools/saipen_engine/improve_retrospective.py | New module: DIRECTORY, SCHEMA_VERSION, MAX_RECORD_BYTES, MAX_HISTORY_FILES, MAX_HISTORY_BYTES; record_path, inspect_archive, write_disposition, reconcile_archive, retire_archived, validate_record; private _fail, _json, _sha, _native_hash, _prove_owned, _owned_bytes, _snapshot, _header, _proof, _native_receipt, _read, _view, _admit, _append |
| tools/saipen_engine/continue_fallback.py | cycle_liveness, new _other_cycle_liveness, stale_cycles, with_cycle_liveness |
| tools/saipen_engine/journal.py | RETROSPECTIVE_POLICY, VERIFICATION_POLICIES, OP_CLASSES, _verifier_for, new verify_improve_retrospective |
| tools/saipen.py | _improve sweep-queue/sweep/reconcile/retire branches |
| tools/saipen_engine/admission.py | PROTECTED_CANONICAL_NAMESPACES |
| tools/saipen_engine/capability.py | guard_core_mutation |
| tools/test_t1803_archived_improve.py | New ArchivedImproveTests, 36 semantic controls |
| tools/test_t38_improve_cycle_liveness.py | CycleLiveness, PayloadMerge archived empty/pending controls |
| saipen/IMPROVE.md | Section 14 terminal qualification; section 15 successor contract |

audit_manifest.py is byte-identical to the mission preimage.
_require_cycle_amendable, complete_report, abort_cycle and ordinary active
mutation semantics retain their prior meanings.

## RED/GREEN TEST RESULTS

Initial RED-full.txt, E-16191: 23 controls, 12 failures, 9 errors, 2 passing
baseline guards, before implementation. The initial fixed oracle had 35 tests;
the expanded fixed oracle after the malformed-JSON input-shape correction has
36 tests (the original 35 test/helper bodies remain AST-identical, verified by
audit-current.py).

Initial 35-control native receipt (E-16200 FAIL / E-16201 PASS):
.saipen/evidence/regression/regression-execution-28221e1520e04f51905fb49a1349c162.json

- Before: 35 ran, 31 failed, exit 1; subject
  860c1fe6ec72e6db8e88534acadcb8219d96340b02ff847fc2af44d47db09ad6.
- After: 35 ran, 0 failed, exit 0; subject
  ad6bbb6e91e29de05c7c1789b427f79492c5715536cd4b00e2d223c38de68484.
- Identical verifier for both:
  179ae2bf179aa0b76e7b21abbbbfb6f99d0c158db07f84fbee792df27cb4cedf.

Terminal 36-control native receipt (E-16213 FAIL / E-16214 PASS):
.saipen/evidence/regression/regression-execution-03021bf78888435586d52547675edcef.json

- Before: 36 ran, 6 failed (all 6 malformed JSON shapes in
  test_malformed_successor_returns_blocked_without_writes), exit 1; subject
  ad6bbb6e91e29de05c7c1789b427f79492c5715536cd4b00e2d223c38de68484.
- After: 36 ran, 0 failed, exit 0; subject
  69943c370d1a48071c5ad0fa87b5ac011c935b12832a04c5f03dbdb7724c0011.
- Identical verifier for both:
  77a06e7522dbcf106390287fff4361fa8842602b56f80c40efdf0a91987e56ee.

regression-contract.json and schema-regression-contract.json fix argv, context,
oracle, subject and before mappings. engine-before/ and schema-before/ preimage
hashes were rechecked.

## FULL REGRESSION RESULTS

Recorded focused evidence: 36 controls PASS (native-schema-regression-result.json),
34 Improve neighbors PASS (GREEN-final-improve-neighbors.txt), 11 liveness
and 5 empty-draft controls PASS at E-16193.

Initial full family at E-16197: 6791 ran, 2 new reds in writer registration.
Record: .saipen/evidence/core-unit/de39bbd33e86d519-20261016T184906Z.json.
Subsequent full family at E-16204 (pre-schema-fix): 6791 ran, 0 red, 0 new red.
Record: .saipen/evidence/core-unit/7be195543407e24b-20261016T213552Z.json.

Terminal full family at E-16215 (current tree 5ae5099b9be8a46b):
python -B tools/core_unit.py evidence T-1803
Record: .saipen/evidence/core-unit/5ae5099b9be8a46b-20261016T232757Z.json
(sha256: 0897c950d1ad01e34f12545ad8cb41ea75125fbc869d81060ec9427a540cdc37).
Output: core-unit-schema.txt.
Result: PASS, 6792 ran, 0 red, 0 new red, 0 problems, 0 leaked sandboxes.
DONE T-1695 re-verified with executed focused contract (RV-000083, CURRENT_PASS,
38/38 passed). Strict-core conformance passed (conformance-schema.json,
receipt-db85d1fb8ab3, CURRENT_PASS, 0 problems).

## RESTART ACCEPTANCE

historical-restart-acceptance-resumed.json and restart_acceptance.py exercise original
historical bytes on disposable admitted projects. Both actual archives have
two draft seats and three findings each:

| Cycle | Content seat | Empty seat | Original identities |
|---|---|---|---|
| imp-vacterro-audapack-20260918-1 | buffy-01/saipen_improve_SAIPEN.md | buffy-02 | RUN-1/IMP-001, IMP-002, IMP-003 |
| imp-vacterro-audapack-20260919-7 | buffy-02/saipen_improve_SAIPEN.md | buffy-01 | RUN-1/IMP-001, IMP-002, IMP-003 |

Copies alone receive NEEDS_EXTERNAL_EVIDENCE dispositions. Fresh-process native
continuations without --dry-run keep all six findings visibly blocked without stale actionable
advertisement. All original report statuses, hashes and absent SWEEPs remain.
No actual consumer successor is created and actual T-311 remains BLOCKED.
Separate fixed-oracle controls prove resolved-copy successful reconciliation,
restart persistence, repeated continuation, PREPARED abort, VERIFIED crash
roll-forward and changed-dependency conflict.

## FORENSIC EVIDENCE POLICY

FORENSIC-POLICY.md defines a bounded opt-in improve_forensics_v1 adjunct:
explicit cycles, at most 8 cycles / 32 seats / 128 findings / 2 MiB total,
truthful omissions, original/sanitized digests, and existing credential,
private-body, cache, lock, staged-payload and transient exclusions.
The adjunct grants no authority.

manifest-policy-observation.json distinguishes v3 directory selection from
its exclusion predicate. Neither Improve tree is selected by the current
export contract. Deploying the adjunct needs a separate versioned
producer/consumer transition and consumer admission. This mission deploys
no export-contract change and modifies no AUDAPACK consumer code.

## CROSS-PROJECT REGRESSION ASSESSMENT

The fixed oracle covers active/terminal behavior, ordinary archive refusal,
NO_GO, missing admission/owned Work, foreign actors, direct-file/producer
protections, native receipt forgery, stale/concurrent writes, compaction,
old policy rejection, malformed JSON event/proof-map shapes, and
interruption/restart. Neighboring lifecycle tests and the declared family
(6792/0/0) test surrounding engine contracts.

Disposable checks are not live acceptance in every managed project. Live
AUDAPACK evidence is bounded read-only identity/hash/record inspection.
No Source closure, conformance, provenance, budget or safety-valve gate is
waived, and no unrelated staged bytes are included in mission attribution.

Graph limitation: Tier 2 saipen generation 2026-09-01T13:16:39Z excludes
tools/. Coverage checks and zero graph matches were followed by direct current
source reads, exact preimage comparisons and executed evidence. No graph
completeness claim is made. Security/performance directories contain example
templates only and declare no applicable extra scanner or benchmark here.

## REQUIREMENT-TO-EVIDENCE AUDIT

The canonical contract remains the closure denominator. All 36 fixed-oracle
tests pass in the native before/after pairs (E-16200/E-16201 and
E-16213/E-16214), and the full declared family passes (6792/0/0 at E-16215).

| SRC-261 clause | Exact evidence coverage |
|---|---|
| R001 | E-16190 authority inspection, canonical Work, current-audit HEAD/version/source integrity and unchanged authority fields |
| R002 | 13 protected path entries unchanged, actual T-311 BLOCKED, disposable-only acceptance code |
| R003 | Current source and baseline-observation reproduction of all seven named behaviors |
| R004 | Two original manifests/four reports/six exact findings in baseline-observation and current-audit |
| R005 | Original-history hash assertions, unchanged missing SWEEPs and drafts |
| R006 | Snapshot/header/native-prefix receipt/append and versioned journal verifier |
| R007 | Owned verification proof control; truthful pending external-evidence and append-only correction |
| R008 | Secondary-seat, terminal unfinished-finding, blocked-retirement, sweep-queue, and malformed-JSON finite-blocker controls (regression-execution-03021bf78888435586d52547675edcef.json) |
| R009 | Exact retry, conflicting duplicate, concurrent and stale-CAS controls |
| R010 | PREPARED abort, VERIFIED fresh-process roll-forward, dependency conflict, repeated continuation |
| R011 | Existing COMPLETE/SUPERSEDED/BLOCKED_EXTERNAL vocabulary; no new phase |
| R012 | test_empty_archive_is_not_advertised_as_pending |
| R013 | test_secondary_seat_findings_are_visible; partial sweep |
| R014 | test_terminal_status_does_not_hide_unfinished_findings; external-evidence visibility |
| R015 | test_first_historical_disposition_preserves_original_missing_sweep |
| R016 | test_partial_sweep_is_preserved_and_combined_with_successor |
| R017 | Exact retry and conflicting duplicate tests |
| R018 | Concurrent disposition and interleaved stale-plan tests |
| R019 | Original-history change, stale plan CAS, checkpoint dependency verification |
| R020 | test_wrong_lineage_cannot_reuse_successor |
| R021 | Missing public admission and missing active Work tests |
| R022 | Foreign actor and producer mutation refusal tests |
| R023 | Interrupted append, dependency conflict and fresh-process VERIFIED crash controls |
| R024 | Fresh-process persisted reconciliation and historical-copy native continuation |
| R025 | Resolved-archive repeated advertisement and native CLI continuation controls |
| R026 | Ordinary active Improve neighbors and retrospective active-target refusal |
| R027 | test_genuinely_complete_cycle_keeps_existing_terminal_behavior |
| R028 | test_no_go_binding_brake_refuses_retrospective_mutation |
| R029 | Producer/foreign/forgery/current-confirmation guards, unchanged safety/budget fields, consumer T-311 unchanged, and 6792/0/0 full family PASS (.saipen/evidence/core-unit/5ae5099b9be8a46b-20261016T232757Z.json) |
| R030 | FORENSIC-POLICY, manifest-policy-observation, audit_manifest preimage equality |
| R031 | Native regression pairs E-16200/E-16201 and E-16213/E-16214 PASS, full family 6792/0/0 PASS (.saipen/evidence/core-unit/5ae5099b9be8a46b-20261016T232757Z.json), conformance CURRENT_PASS (conformance-schema.json, receipt-db85d1fb8ab3) |
| R032 | CAS/dependency/native-prefix source review, race/restart controls, actual historical-copy acceptance |
| R033 | Complete twelve-part report and exact durable evidence in .saipen/evidence/T-1803-archived-improve/ |

## REMAINING BLOCKERS

The malformed-JSON input-shape defect identified during self-review in
improve_retrospective._read (event [] and non-dict evidence maps) was repaired
in E-16206 and verified by the native 36-control RED/GREEN pair at
E-16213/E-16214 (.saipen/evidence/regression/regression-execution-03021bf78888435586d52547675edcef.json)
plus the 6792/0/0 full core-unit family at E-16215.

The engine implementation for T-1803 / SRC-261 has no remaining blockers.
Actual AUDAPACK findings remain untouched under their independent consumer owner
(AUDAPACK T-311 BLOCKED, 13 protected path digests unchanged). Remote Git
publication remains disabled under mode: no-publish (policy pending T-1644).

## NEXT EXACT ACTION

Settle SRC-261:R008, R029, R031, and R033 to VERIFIED, checkpoint VERIFY PASS,
transition T-1803 to REVIEW, execute independent REVIEW verification, and
complete local no-publish SHIP / ticket closure before continuing canonical
routing to SRC-262 and T-1804.
