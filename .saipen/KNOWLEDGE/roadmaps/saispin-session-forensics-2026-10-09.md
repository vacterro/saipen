# SAISPIN session forensic audit and execution safety debt — 9 October 2026

STATUS: PENDING_ADMISSION (consumer findings); receiving-project intake recorded as SRC-198 / T-1692.
CURRENT_PROJECT_STATE: SAITULS raw BUILD T-271, last_event 2772; canonical VALIDATION_FAILED.
CURRENT_HEAD: 5723d53894cc2b279de8dc2a4c3b2dce169f421f; six product/test files untracked, content identities in snapshots.
T-271_STATUS: raw DOING P2, owner saipen-cli; preserved, no ownership or checkpoint change.
T-273_STATUS: raw DOING P1, owner saipen-cli, SRC-092; no successful closeout; canonical allocation event missing according to the engine.
SRC-092_STATUS: ACTIVE, original mission unchanged; new exact SRC-093 append RECEIVED/unprojected, no linked Work or accepted clauses.
FINDINGS_RECORDED: F-01 through F-07 classified in this local incident reference; consumer admission refused, not claimed stored as accepted Work.
EXISTING_TICKETS_REUSED: T-273/SRC-092 proposed product safety and verification boundary; T-1671/T-1672 lifecycle/activation and T-1647/T-1652/T-1653 host/account boundaries; T-1644 publication boundary.
NEW_TICKETS: receiving-project T-1692 intake candidate only; zero consumer tickets, zero speculative engine implementation tickets.
CONFIRMED_DEFECTS: current canonical two-DOING floor and missing allocation refusal; bounded current lease verifiers do not authenticate an issuer.
UNVERIFIED_RISKS: real issuer/storage ACLs, authorization replay/revocation/progress safety, current arming, original writer/admission, behavioral regressions and live acceptance.
CONCURRENCY_ASSESSMENT: current floor invalid; both raw owner claims preserved; legal parallel admission/scopes not proven; watcher changed concurrently and both generations retained.
CURRENT_AUTO_KILL_SAFETY: UNVERIFIED; no safe-real-process claim; require alert/dry operation for affected unsafe recovery until authorized proof, preserve visibility.
TEST_EVIDENCE_GAPS: reported PASS, empty discovery, nine failures and permission denials separated; original streams/exit codes/revisions unavailable; no product tests executed by intake.
REQUIRED_OPERATOR_GATES: consumer owner adjudicates checkpoint/identity and write-scope admission; trusted recovery design and controlled hermetic Windows acceptance; genuine elevation/namespace capability and applicable authorization; actual managed-account host acceptance remains separate.
NEXT_AUTHORIZED_ACTION: consumer canonical owner resolves the refused checkpoint/identity using actual durable evidence, then admits SRC-093 through canonical source apply-append; protocolist continues SAIPEN hardening, no product repair.

Target: SAITULS T-273 / SRC-092. Related active Work: T-271.
Source: SAIPEN SRC-198 / T-1692, the operator's complete incident intake.
Scope: record, classify, deduplicate and route; no product implementation,
runtime changes, live termination tests, ownership recovery or acceptance.

## Evidence and priority

The operator requests P0 triage. F-01/F-02 are critical safety findings;
F-03 is a P0 execution-control investigation, F-04/F-05/F-06 are P1 and
F-07 is P2. These finding severities do not silently change T-273's observed
BOARD priority P1 or create seven new tickets. The receiving SAIPEN engine
records the unwitnessed ingress honestly as a P2 candidate (model_supplied).

The handoff reports confirmed session observations. Its original transcript,
test streams, revisions and exit statuses were not supplied. Those observations
remain attributed to SRC-198, separate from independently read current bytes.
Current source checks are static; they prove neither historical authorship
nor behavior, trusted runtime authorization or live Windows acceptance.

Read-only current checkout: HEAD 5723d53894cc2b279de8dc2a4c3b2dce169f421f.
The six named product/test files are untracked, so HEAD does not identify their
contents. Stable byte copies and SHA-256 values are preserved in the receiving
project at .saipen/evidence/T-1692-saispin-forensics/snapshot.json and snapshot/.
At 2026-10-09T00:22:24Z the watcher had changed concurrently, while all ten
other named files were unchanged. A second immutable snapshot at 00:24:12Z
records the new watcher SHA-256
6c57104051ef535c617ab1ac0f709fa53bb09b012e494672201e45c19e0ef38e.
No writer identity or acceptance is inferred from that change.

## Current authority and concurrency

STATE is BUILD T-271, actor saipen-cli, last_event 2772. BOARD contains T-271
and T-273 in DOING; both claim owner saipen-cli. T-273 names SRC-092 and is P1.
SRC-092 is ACTIVE and already requests trusted ownership, safety, hermetic
fixtures, real test entry points, live Windows proof and explicit arming.

The consumer's canonical status command exits 1 with VALIDATION_FAILED:

    checkpoint invalid: FLOOR: STATE.task=T-271 but BOARD DOING has multiple openers at the raw floor; BOARD proposed has more than one ## DOING ticket

Its diagnostic action is saipen recover. This intake does not run that action
or rewrite the checkpoint. Two DOING entries alone do not prove an ownership
collision or that historical parallel execution was forbidden. No T-273 or
SRC-092 entry was found in the bounded current LOG snapshot; older journals,
other channels and the original host admission were not exhaustively searched.
The attempted canonical append projection independently reports that T-273
has no allocation event in its complete-history check (CORE-003 /
SRC-026:R003). That is an engine finding about the current checkpoint, not
proof of a specific writer's identity. No retroactive authorization is inferred
or fabricated.

## Findings and present classification

| Finding | Current evidence / remaining requirement | Owner and route |
|---|---|---|
| F-01, P0 | Reported settings-dependent lease bypass; current decide() calls evaluate_recovery_lease(sample) unconditionally before KILL. Static correction present; same-oracle pre-fix RED, positive/negative behavior and live acceptance unverified. | Existing T-273 / SRC-092, product executor saipen-cli; preserve and prove the correction. |
| F-02, P0 | Current evaluate_recovery_lease() checks exact PID/start_time, authorized is True and expiration against sample.observed_at, without authenticating an issuer or a trusted revocation state. The first watcher snapshot lacked final lease revalidation. The concurrent second generation adds Get-RecoveryLeaseVerdict() and a live-clock lease re-read immediately before Stop-Process; that complete new verifier still authenticates no issuer. Static progress is recorded; behavioral proof remains absent. | Existing T-273 / SRC-092, product executor; define trusted issuer, protected store and prove final termination authorization. |
| F-03, P0 investigation | Edits-before-admission sequence reported; current contradictory floor and missing canonical T-273 allocation are independently reported by the canonical engine. Original host admission, actual writer identity and legitimate parallel write scopes remain unproven. | SAIPEN T-1692 bounded incident investigation; reuse T-1671/T-1672 lifecycle/activation work and T-1647/T-1652 managed-host boundaries. Engine owner must reproduce an enforcement defect before new implementation work. |
| F-04, P1 | Production-visible lease fixture writes reported. Current Python tests redirect leases to mkdtemp, but import mutates SAISPIN_LEASE_DIR; bounded full-file cleanup search finds no prior-environment restoration or directory cleanup. Settings tests use disposable paths and finally cleanup. Task tests use a fixed T135TEST/T135 namespace and remove it without restoring a preexisting fixture task. | Existing T-273 / SRC-092 verification/fixture scope; product executor. Historical T-135/T-136 are references, not automatically reopened. |
| F-05, P1 | Reported direct-script PASS, empty pytest discovery, task failures and permission denials are independent outcomes. Current declared-suite status is undeclared with no newest receipt; it does not invalidate the documented direct-script harness or prove all tests absent. | Existing T-273 / SRC-092; product verification owner. Preserve process status, discovery counts, exact source and evidence identities. |
| F-06, P1 | Repeated privileged denial/UAC attempts reported. Current task harness performs real ScheduledTasks operations; static inspection of its full body finds no token/namespace capability preflight before registration. No such fixture was executed in this intake. | Existing T-273 / SRC-092 verification owner; capability preflight and STOP, without autonomous UAC or unchanged retries. |
| F-07, P2 | Late authority, redundant work and weakened safety oracle reported; original transcript not independently supplied. | Reuse BOOT entry, PHASE-DELTA-01 and VERIFY-ORACLE-01; retain incident evidence instead of adding parallel global rules. |

The current F-02 absence claims are bounded to the complete named functions,
not a claim that no issuer/ACL mechanism exists anywhere. Storage ACLs,
actual issuer behavior, revocation and replay protection remain unverified.
Graph project SAITULS generation 2026-09-23T14:49:26Z is stale for these changed
files; current Python/PowerShell AST source reads are the evidence. Relevant
coverage was checked; unrelated Scripts/tests coverage gaps do not support
whole-project negative claims.

## Deduplicated delivery and acceptance

Reuse one product safety work boundary, T-273 / SRC-092, and its verification
scope rather than creating seven work items. If its authorized executor needs
independent fixture/verification delivery, that owner may split one scoped P1
child after canonical coordination; no such child is created by this intake.
Keep protocol execution-control investigation separate from product code.
Existing T-1671/T-1672 engine work is locally verified but its activation and
acceptance remain blocked; this does not prove that the observed host enforced
pre-write admission. Antigravity registry admission/style/final capabilities
are ADVISORY, with no declared delivery hook. Installed/loaded host evidence
and a global invariant failure are not established here.

H-01 through H-05 remain hypotheses: advisory pre-write admission, concurrent
STATE/ownership reconciliation, misleading verification, fixture isolation and
capability-aware STOP. The existing floor check correctly refuses the current
shape. This incident creates no demonstrated global blocker or new global law.

The authorized product executor must preserve SRC-198 acceptance A-L:

1. Unknown ownership, missing/malformed/expired/revoked/mismatched authorization
   and PID reuse must refuse termination. Bind issuer authentication to exact
   process identity; filename, command line, CPU, orphan status and a writable
   JSON flag alone are insufficient.
2. Active agents/tests/renders/compilers survive. Resumed progress invalidates
   stall evidence. Configuration normalization and every public entry point
   enforce the same invariant.
3. Decision logic and final PowerShell execution enforce equivalent eligibility
   and independently revalidate immediately before termination, including
   revocation during the sweep. Only an explicitly disposable managed worker
   may supply positive controlled recovery proof after every gate passes.
4. Use disposable roots, unique task names and process targets, exact original
   state/environment restoration and failure cleanup. A negative control must
   prove no production-visible authorization write can escape the fixture root.
5. Preserve the original unsafe behavior as RED under the unchanged new oracle;
   do not obtain green by weakening ownership or safety. Report source tests
   and live Windows acceptance separately, both bound to the actual revision.
6. Preflight token elevation, Scheduler availability, namespace permission and
   applicable operator authorization before a privileged fixture. On denial,
   record the missing capability and ENVIRONMENT_BLOCKED/PERMISSION_DENIED;
   retry only after a material relevant change. Do not request UAC autonomously.

Verification evidence must carry command, environment, actual test-process exit
code, collected/passed/failed/skipped/blocked counts (or explicitly unavailable),
fixture isolation, baseline revision, changed source revision and evidence ID.
TEST_DISCOVERY_EMPTY, TEST_FAILURE, ENVIRONMENT_BLOCKED, PERMISSION_DENIED and
PASS stay distinct. Shell grep/tail success cannot replace the test exit code.

## Original test observations — attribution, not current acceptance

| Reported command | Reported result | Classification |
|---|---|---|
| python tests/test_saispin.py | PASS after weakened safety condition | Reported PASS; unsafe oracle, no current acceptance |
| python -m pytest tests/test_saispin.py | 0 items collected | TEST_DISCOVERY_EMPTY, unverified |
| Scripts/saispin_watch.ps1 -SelfTest | PASS in one run | Reported PASS, raw evidence unavailable |
| tests/test_saispin_settings.ps1 | PASS in one run | Reported PASS, raw evidence unavailable |
| tests/test_saispin_task.ps1 | Nine failures in a separate run | TEST_FAILURE |
| Other task fixture invocations | Register-ScheduledTask: Access is denied | PERMISSION_DENIED / ENVIRONMENT_BLOCKED; no live PASS |

The intake executes no product tests and changes no product/runtime/task/ACL
state. A read-only query found no SAITULS/SAISPIN scheduled task visible to the
current account (ObjectNotFound); this is neither an access-denial result nor
proof that every account/context is disarmed. Current auto-kill safety and
actual runtime arming remain UNVERIFIED. Require DRY-RUN or ALERT-ONLY for the
affected unsafe recovery paths until the authorized product fix is proven;
preserve unrelated watchdog visibility and do not kill legitimate processes.

## Required next owner action

Canonical source append accepted the exact original incident text as SAITULS
SRC-093, amending SRC-092, APPEND/evidence, SHA-256
b2001ebab6a8da415d929baafe23bab371ce3564bf23951067b8a34eacdd0502
(15837 bytes). Its journal event is null and its ledger remains RECEIVED,
unprojected, with no linked Work. Canonical apply-append exited 1:

    VALIDATION_FAILED: proposed state fails fast validation: FLOOR: STATE.task=T-271 but BOARD DOING has multiple openers at the raw floor; BOARD proposed has more than one ## DOING ticket; BOARD: T-273 has no [T-###] allocation event in the complete history -- ticket identity comes from canonical allocation, never from a record that merely looks like a ticket (CORE-003 / SRC-026:R003)

The captured body is not an admitted finding or an implemented amendment.
No consumer ticket was created, and STATE, BOARD and LOG stayed byte-identical.
Recording/projection is PENDING_ADMISSION; the same failing operation is not
retried, and no manual journal or ownership repair is attempted.

The SAITULS canonical owner must establish a valid current checkpoint and
durable T-271/T-273 admission/write-scope evidence through its own canonical
operations, preserving historical records and ownership. Admit this amendment
only then, reconcile it against SRC-092, and execute the bounded product work.
The protocolist records the exact recording refusal and pending amendment;
it does not claim this text was merged into the consumer or any fix completed.
