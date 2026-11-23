# Resilience remediation handoff — proposed, not executed

Authority: SRC-215 authorizes audit and this queue, not runtime implementation
or publication. Reuse existing Work where named; these identifiers do not
create duplicate canonical tickets or grant permissions. REPORT.md owns the
finding evidence and component attribution. Priorities are evidence-adjusted;
no new P0 escape was demonstrated.

## RSL-01 — P1 / existing T-1715: reject borrowed lifecycle reservations

Depends on: none. Finding F01. Owner: operations._ticket_targets and dependency
resume; tests adjacent to test_dependency_resume_liveness.
Implement the already declared owned active-parent handoff predicate before
any mutation. If TODO ordering is required, specify a separate scheduling edge
that cannot save another Work's phase. Keep plain TODO blocking legal.
Acceptance: C's bad TODO parent refuses with every canonical byte unchanged;
active owned handoff preserves its own resume phase; wrong actor/session,
self/nonworkable/duplicate child refuse; child completion restores no synthetic
claim; restart/replay cannot skip SCOUT/BUILD. Full declared family and source
contract checks pass. Preserve E-14412 and all later history. No data migration
by guessing intent; inspect old records under a separately owned recovery.

## RSL-02 — P1: publish a versioned read-only capability contract

Depends on RSL-01 for the corrected handoff feature declaration. Findings
F02/F04/F06. Owners: commands, runtime_surface, host_integration, CLI and skill
transport; reuse their schemas and registry.
Add supported command/effect/producer/schema/profile metadata, observed versus
declared capability, source/installed/loaded identities and explicit unknown
values. The handshake grants no mutation. Resolve cc-all grammar at that
owner: documented zero-write refusal or explicitly equivalent continuation,
never implicit gg or authority reset.
Acceptance: old/new skill and runtime matrix, unknown future schema, no loaded
proof, stale install, malformed payload and JavaScript regression consumer;
documented routes match real public argv and guard admission. Bootstrap and
read-only inspection remain reachable. No installation or release inside this
ticket unless separately authorized by its concrete scope.

## RSL-03 — P1: unify operation-scoped continuation diagnostics

Depends on RSL-02. Findings F07 and observed historical router/guard mismatch.
Owners: admission, remediation, reconcile, router and automation.
Extend the existing typed decision with failed invariant, complete affected
targets/domain, independent admitted lane, existing recovery route and exact
human boundary. NORMAL/DEGRADED/QUARANTINED/HARD_STOP are projections, not new
STATE phases. One owner computes runnability; transports consume it.
Acceptance: target disjoint/overlap/unknown matrix; corrupt common history
never permits canonical mutation; reads remain; named recovery route is
admitted and actually clears a repairable fixture; missing-parent terminal
case names no impossible repair; no claim theft or duplicated effect. Retain
existing strict/advisory host distinctions and publication capability.

## RSL-04 — P1: make observation capture and promotion explicit

Depends on RSL-02 and RSL-03. Findings F03/F06/F07.
Owners: evidence storage, regression_execution/log, journal/plan/reconcile.
Specify immutable non-authoritative observations with provenance and failed
admission reason. Promotion must execute the supported producer and recheck
all active authority/input bindings at commit. Add managed verifier invocation
metadata and nonsecret context-change categories; do not weaken identity by
silently ignoring environment/runtime changes.
Acceptance: stale/current Attempt, changed acceptance/contract/prior/oracle,
forged producer, missing ancestry, observation replay and receipt tampering
all refuse authority; genuine native Python and Node pairs admit; zero-test,
timeout and launch error cannot be observations promoted to PASS. Crash at
each durable boundary recovers to zero or one committed operation; repeat
recovery preserves all originals and adds no second transition.

## RSL-05 — P1: bounded model, fault and cross-version controls

Depends on RSL-01 through RSL-04, with tests developed alongside each change.
Owners: existing production test modules and declared family harness.
Implement REPORT I01–I10 as a small reference model with bounded generated
sequences and shrinking. Deterministic seeds, explicit tested bounds and
counterexamples belong in evidence. Add process-death and concurrent
precondition changes, alias/case path variants, replay and cross-version
producer/reader fixtures. Exercise Windows and Linux where actually available.
Acceptance: known bad preimages or mutations make the same oracle fail;
unsafe effect/authorization controls remain red-as-expected, legitimate lanes
pass, no unit count invented, source and consumer generations explicit.
Claim only tested coverage; unavailable real hosts remain external evidence.

## RSL-06 — P2: record interpretable resilience telemetry

Depends on RSL-03 and RSL-05's classifications. Owner: existing typed
telemetry/status and independent review, not a competing success predicate.
Implement REPORT's seven KPI definitions with intent/episode dedupe,
classification provenance, unknown coverage, censoring and immutable cohorts.
No success-rate gate until real measured denominators are reviewable.
Acceptance: synthetic labeled fixtures yield exact known counts; retry spam,
ticket splitting, unclassified failures, open episodes, planned authorization
and renamed cause IDs cannot silently improve a rate. Source data never
contains secrets and metric collection grants no lifecycle authority.

## RSL-07 — P1, separate delivery boundary: prove installed and loaded contracts

Depends on reviewable authorized source scope plus RSL-02; scheduled delivery
must obey the existing publication owner and no-publish policy.
Owner: installer/host freshness; not the audit ticket. Reconcile each stale or
unknown home to an explicitly approved artifact, then prove a newly loaded
session's generation and capability contract. Do not stage the unrelated
215-path dirty surface from a diagnostic suggestion.
Acceptance: actual per-home installation and fresh-session proof, correct
unsupported-host degradation, rollback retaining receipts and instructions,
consumer T-31 acceptance only in its own authorized owned continuation.
DIRTY_SOURCE is a correct boundary until this separate process is authorized.

## RSL-08 — P2 investigation before enforcement: resolve live capability versus mode

Depends on none for read-only investigation; any fix depends on a proven
supported producer sequence and CORE/capability owner's contract decision.
Finding F05. Owners: capability and admission.
Reconstruct a real read-only-handshake then full/no-publish session without
manually altering canonical state. If the conflict occurs, remove reliance on
historical mode only according to the authoritative live-capability contract.
Acceptance: no stale full state grants a read-only session writes; stale
read-only state does not deny a genuinely authorized live session if that is
the resolved contract; direct canonical writes and foreign claims remain
closed. If no supported producer can cause it, report the synthetic limit and
close the investigation honestly without broadening admission.

Sequence: RSL-01 → RSL-02 → RSL-03 → RSL-04 → RSL-05 → RSL-06.
RSL-07 is a separate authorized delivery branch; RSL-08 is an investigation
branch. Root SRC-205 and existing T-1715 retain their actual scope/status.
