# FUTURE GATE — DURABLE AUTONOMOUS RUNS

## STATUS

Shelf / long-horizon design reference.

Do not activate while current SAIPEN control-plane, executor-admission, cross-user runtime, multi-profile launch, or protocol-integrity work still has higher-priority unfinished prerequisites.

## INTENT

Evolve SAIPEN from a durable protocol around tickets/phases into a durable autonomous execution runtime.

The long-term invariant:

> Work must survive the death or replacement of the model, provider, process, host session, account session, and compatible runtime instance.

A `/goal` is not merely a prompt instruction.

A `/goal` should become a durable logical Run with:

- stable identity;
- explicit lifecycle;
- checkpoint/resume semantics;
- typed waits;
- executor attempts;
- idempotency;
- replay boundaries;
- capability-aware scheduling;
- version/runtime pinning;
- traceability;
- machine-readable outputs.

## WHY THIS EXISTS

SAIPEN already has many of the necessary lower-level primitives:

- STATE;
- BOARD / Work;
- LOG / evidence;
- execution intent;
- canonical continuation;
- executor admission;
- typed blockers;
- lifecycle phases;
- cold recovery;
- host integration;
- response rendering;
- future gates.

The remaining weakness is that durable execution is still distributed across those surfaces.

The system increasingly behaves like a durable workflow engine, but does not yet expose one canonical durable Run object as the owner of autonomous execution.

The next architectural mutation should unify those concepts.

---

# 1. DURABLE RUN

Introduce a first-class canonical Run identity.

Conceptual form:

RUN-000123

A Run should represent one durable autonomous execution trajectory.

Suggested machine fields:

- run_id
- project_id / project_root identity
- execution_intent
- goal/source authority
- created_at
- started_at
- current_ticket
- current_phase
- current_attempt
- status
- protocol_generation
- runtime_generation
- schema_generation
- executor_history
- checkpoint_id
- waitpoint_id
- parent_run_id
- child_run_ids
- retry_policy
- terminal_reason
- evidence_refs
- output_refs
- operator_action_due
- updated_at

Do not require this exact schema.

The invariant matters more than field names.

## Run status

A future Run state model may distinguish:

- CREATED
- READY
- RUNNING
- CHECKPOINTED
- WAITING
- RETRYING
- FAILING_OVER
- BLOCKED
- COMPLETED
- FAILED
- CANCELLED

Avoid duplicating existing ticket/phase state.

Run state should describe orchestration state above Work lifecycle.

---

# 2. CHECKPOINT / RESUME

## Goal

A compatible executor should resume a Run from a durable boundary without reconstructing execution from conversation prose.

Checkpoint identity should bind to the state necessary to continue safely.

Potential checkpoint contents:

- Run identity;
- current Work;
- current phase;
- exact repository/tree fingerprint;
- protocol/runtime generation;
- accepted evidence;
- completed sub-results;
- pending waitpoint;
- retry/attempt counters;
- executor capability requirements;
- unresolved effects;
- canonical next route.

## Required invariant

After a crash, OOM, host restart, provider logout, model swap, or application restart:

Run -> checkpoint -> compatible executor -> canonical resume.

Not:

chat transcript -> model interpretation -> guessed continuation.

## Checkpoint boundaries

Candidate durable boundaries:

- after successful SCOUT;
- after BUILD mutation is durably committed to project bytes;
- after VERIFY evidence is accepted;
- after REVIEW;
- before/after irreversible SHIP operations;
- before WAIT_USER / WAIT_EXTERNAL;
- before executor release;
- after external side-effect acknowledgement.

Do not checkpoint blindly after every tool call.

Use semantic boundaries.

---

# 3. ATTEMPT MODEL

Separate durable Work from one executor's attempt to execute it.

Example:

T-123
- ATTEMPT-1: executor incompatible
- ATTEMPT-2: transient Windows sharing violation
- ATTEMPT-3: implementation succeeds

The ticket is not "three different broken tickets."

An Attempt should make executor/runtime failure explicit.

Potential fields:

- attempt_id
- run_id
- ticket_id
- phase
- executor_id
- capability_fingerprint
- started_at
- ended_at
- outcome
- failure_class
- retryable
- evidence_refs
- resource usage
- predecessor_attempt_id

## Important distinction

Failure classes should route differently:

- project defect;
- test defect;
- executor incompatibility;
- provider outage;
- transient filesystem conflict;
- runtime mismatch;
- operator wait;
- external wait;
- protocol contradiction.

Do not flatten them into one generic retry count.

---

# 4. TYPED WAITPOINTS

Replace vague waiting with explicit durable wait objects.

This is one of the highest-value mutations.

Conceptual object:

WAITPOINT-00042

Fields may include:

- waitpoint_id
- run_id
- reason_class
- created_at
- timeout_at
- expected_schema
- allowed_responses
- completion_authority
- completion_status
- completion_payload
- idempotency_key
- resume_route
- evidence_refs

Possible statuses:

- WAITING
- COMPLETED
- TIMED_OUT
- CANCELLED

## Use cases

- operator approval;
- operator choice;
- external service completion;
- file arrival;
- deployment approval;
- native machine acceptance;
- account authentication;
- scheduled delay.

## Operator-question invariant

A UI question should be the rendering of a canonical waitpoint.

The model must not invent lifecycle choices.

If no waitpoint exists and machine disposition is CONTINUE:

no operator question.

## Typed output

A waitpoint may expect:

approve | reject

or a structured payload.

The completion result becomes machine input to the Run.

This removes prose ambiguity.

---

# 5. IDEMPOTENCY

Durable autonomous execution needs idempotent commands and side effects.

Candidate idempotency identity:

operation_type
+
run_id
+
ticket_id
+
phase
+
tree/input fingerprint
+
effect identity

Examples:

- phase transition;
- finish ticket;
- waitpoint creation;
- waitpoint completion;
- test evidence registration;
- release preparation;
- external publish request;
- account/runtime provisioning.

Repeated equivalent requests should resolve to the same canonical result when safe.

## Required behavior

Duplicate host event, repeated retry, reconnect, or double-send must not:

- finish a ticket twice;
- create duplicate waitpoints;
- duplicate irreversible side effects;
- create conflicting evidence generations;
- double-publish a release.

---

# 6. RETRY POLICY

Retries should be explicit and failure-class-aware.

Do not use one generic "retry 3 times" rule.

Potential policy dimensions:

- retryable failure classes;
- maximum attempts;
- backoff;
- jitter;
- same executor vs failover;
- same account vs alternate account;
- same provider vs alternate provider;
- checkpoint reuse;
- operator escalation threshold.

Examples:

TRANSIENT_FILE_LOCK
-> bounded same-executor retry

EXECUTOR_INCOMPATIBLE
-> no same-executor retry
-> failover immediately

PROVIDER_OUTAGE
-> checkpoint
-> alternate provider if policy permits
-> otherwise WAIT_EXTERNAL

PROJECT_TEST_FAILURE
-> no blind retry
-> return to repair lifecycle

---

# 7. SELECTIVE REPLAY

A durable Run should support replay from a safe semantic boundary.

Examples:

replay from VERIFY checkpoint
replay current Attempt
replay external acceptance
replay failed child Work

Do not equate replay with "run the whole ticket again."

## Critical rule

Never repeat irreversible effects unless their idempotency contract proves replay safe.

Replay should consult:

- checkpoint;
- effect ledger;
- evidence fingerprints;
- idempotency keys;
- current repository state.

---

# 8. CACHED / REUSABLE COMPLETED RESULTS

If an earlier phase result remains valid for the exact required fingerprints, reuse it.

Example:

SCOUT -> valid
BUILD -> valid
VERIFY -> valid
SHIP attempt fails because provider API is unavailable

A later retry should not automatically redo SCOUT/BUILD/VERIFY if their exact evidence remains current.

This is not permission to reuse stale proof.

Reusability requires explicit validity identity.

Potential key:

result_kind
+
input/tree fingerprint
+
contract version
+
runtime/protocol generation where relevant

---

# 9. CAPABILITY-AWARE QUEUES

Generalize executor admission into queue/lane scheduling.

Potential lanes:

- full_coding
- read_only_audit
- windows_native
- gui_acceptance
- browser_interaction
- privileged_helper
- cheap_fallback
- premium_reasoning
- long_context
- local_offline

A Work/Attempt declares required capabilities.

An executor declares currently available capabilities.

Scheduler admits only compatible executors.

## Benefits

This should make DEAD-ON-ARRIVAL handoffs structurally impossible.

A C# BUILD requiring:

- repo_write
- shell
- csharp_build
- test_exec
- saipen_control

must never enter a read_tabular-only lane.

---

# 10. EXECUTOR LEASES

Separate Work ownership from temporary compute/executor occupancy.

A Run may own Work while no model process is currently running.

Lease lifecycle:

acquire
-> execute
-> checkpoint/wait/finish
-> release

## Important wait behavior

WAIT_USER or long WAIT_EXTERNAL should normally release expensive executor capacity.

When the waitpoint completes:

Run reacquires a compatible executor and resumes.

Do not keep a premium model/process alive merely to wait six hours for a human.

---

# 11. VERSION-PINNED EXECUTION

A running Run must know which protocol/runtime contract it belongs to.

Suggested identities:

- protocol_generation
- runtime_generation
- schema_generation
- project migration generation

## Invariant

Updating SAIPEN must not silently reinterpret a live Run under incompatible semantics.

Possible behaviors:

1. continue under the pinned compatible runtime;
2. migrate Run through an explicit tested migration;
3. block with an exact incompatibility diagnostic.

Never:

download latest source
-> assume compatibility
-> continue.

This directly supports cross-Windows-user runtime distribution.

---

# 12. STRUCTURED WORK INPUT / OUTPUT

Move critical Work semantics out of free-form Markdown alone.

A Work envelope may declare:

- ticket id
- phase
- source receipts
- detail ref
- required capabilities
- expected artifacts
- validation contract
- irreversible effect declarations
- allowed operator waits
- output schema

Human-readable handoff remains valuable.

Machine-critical requirements must be structured.

## Validation

Malformed Work input should be rejected before executor handoff.

Malformed executor output should not silently become lifecycle truth.

---

# 13. PARENT / CHILD RUN GRAPH

A long autonomous goal may spawn sub-runs.

Example:

RUN-100 /goal cc all
  RUN-101 project test evidence
  RUN-102 external consumer repair
  RUN-103 GUI acceptance
  RUN-104 cross-repo SAIRoute wiring

Parent completion depends on declared child contracts.

Avoid pretending all work belongs to one linear process.

## Child properties

- independently retryable;
- independently observable;
- explicit dependency on parent;
- explicit result/evidence returned to parent.

---

# 14. TRACE GRAPH

Build a first-class trace:

Run
-> Work
-> Attempt
-> Executor
-> Tool / Process
-> Validation
-> Evidence
-> Effect
-> Waitpoint
-> Resume

Questions that should become mechanically answerable:

- Why did this ticket take four hours?
- Which executor failed?
- How many attempts were made?
- Which evidence authorized SHIP?
- Which waitpoint stopped the Run?
- Which external effect happened?
- Which checkpoint was resumed?
- Which runtime generation executed the Work?

Do not require LOG archaeology for ordinary diagnosis.

---

# 15. REALTIME RUN METADATA

Expose compact current Run state to GUI consumers.

Potential fields:

RUN-123
T-1669
VERIFY
elapsed: 42m
executor: CL2
attempt: 2/3
blocker: none
next: core-unit
last checkpoint: CP-0091

Consumers may include:

- FastPrompter
- ZAICODE
- SAIHOME
- SAITULS
- web dashboard
- CLI status

GUI should consume machine state.

Do not parse agent prose to discover progress.

---

# 16. CANCELLATION

A durable Run needs explicit cancellation semantics.

Distinguish:

- cancel queued attempt;
- stop current executor;
- cancel current ticket;
- cancel entire Run;
- abandon external wait;
- preserve completed evidence;
- rollback only where rollback is actually supported.

Cancellation is not deletion.

Historical trace/evidence should remain durable.

---

# 17. BULK OPERATIONS

Only after Run identity is mature, consider:

- cancel multiple Runs;
- retry failed Runs;
- replay selected Runs;
- reassign executor lane;
- pause/resume;
- mark external wait complete;
- drain a queue.

This may support the long-term many-agents goal.

Do not implement bulk operations before individual Run semantics are reliable.

---

# 18. ENVIRONMENTS / ISOLATION

Potential future distinction:

- DEV
- PREVIEW
- STAGING
- PROD

For SAIPEN this may map more naturally to:

- sandbox/test project;
- disposable acceptance clone;
- live local project;
- publish-capable environment.

The important idea is environment identity, not copying Trigger.dev vocabulary.

A Run must know where its effects are permitted.

---

# 19. OBSERVABILITY WITHOUT OPERATOR NOISE

Detailed trace should be rich.

Operator checkpoint should remain compact.

Use progressive disclosure:

operator:
- status
- blocker
- next
- validation summary

machine:
- full trace
- attempt history
- evidence
- logs
- timings
- retries
- effect ledger

Do not regress OPERATOR-READABILITY contracts.

---

# 20. FAILURE RECOVERY INVARIANTS

Future durable engine should prove at least these scenarios.

## Model death

Executor disappears mid-BUILD.

Expected:
- Attempt fails/interrupted.
- Run survives.
- checkpoint/effect boundary determines safe restart.
- compatible executor resumes.

## Provider outage

Provider becomes unavailable.

Expected:
- checkpoint.
- failover if policy permits.
- otherwise WAIT_EXTERNAL.
- no Work loss.

## Host restart

FastPrompter / ZAICODE / shell closes.

Expected:
- Run survives.
- control plane reconstructs active Run from canonical state.
- no chat transcript dependency.

## Windows reboot

Expected:
- durable Run remains discoverable.
- resumable Work re-enters eligible queue.
- no duplicate irreversible effect.

## Runtime upgrade

Expected:
- pinned Run continues compatibly or migrates explicitly.

## Account change

Expected:
- new executor/account may resume if capabilities and identity policy allow it.

## Duplicate delivery

Same handoff/event arrives twice.

Expected:
- idempotency suppresses duplicate effect.

## Operator wait

Executor released while waiting.

Expected:
- wait completion reacquires compatible executor.

---

# IMPLEMENTATION ROADMAP

## FOUNDATION A — RUN IDENTITY

Deliver:
- canonical Run record;
- stable Run ID;
- link execution_intent to Run;
- current Work/phase projection;
- terminality.

Acceptance:
- one `/goal` creates/reuses one durable Run according to explicit rules;
- Run survives process restart.

## FOUNDATION B — ATTEMPTS

Deliver:
- Attempt identity;
- executor binding;
- typed outcome;
- attempt history.

Acceptance:
- incompatible executor does not corrupt Work;
- failover creates a new Attempt under the same Run.

## FOUNDATION C — CHECKPOINTS

Deliver:
- checkpoint record;
- semantic checkpoint boundaries;
- resume.

Acceptance:
- kill/restart test resumes without transcript reconstruction.

## FOUNDATION D — WAITPOINTS

Deliver:
- typed wait object;
- completion API;
- timeout;
- resume route.

Acceptance:
- WAIT_USER rendered only from canonical waitpoint;
- executor released while waiting.

## FOUNDATION E — IDEMPOTENCY / EFFECT LEDGER

Deliver:
- operation/effect identities;
- duplicate suppression;
- replay safety.

Acceptance:
- duplicate transition/event does not duplicate outcome.

## FOUNDATION F — CAPABILITY QUEUES / LEASES

Deliver:
- compatible lane scheduling;
- lease acquire/release;
- wait releases resources.

Acceptance:
- read-only executor never receives write/build Work.

## FOUNDATION G — VERSION PINNING

Deliver:
- Run runtime/protocol identity;
- compatibility/migration behavior.

Acceptance:
- runtime upgrade cannot silently reinterpret active Run.

## FOUNDATION H — TRACE / REALTIME METADATA

Deliver:
- Run trace graph;
- compact live metadata API.

Acceptance:
- UI displays progress from machine state, not prose.

## ADVANCED I — SELECTIVE REPLAY / CACHED RESULTS

Deliver:
- validity-keyed result reuse;
- replay from checkpoint.

Acceptance:
- retry after late failure does not rerun still-valid earlier phases.

## ADVANCED J — CHILD RUNS / BULK CONTROL

Deliver only after foundations are mature.

---

# MIGRATION STRATEGY

Do not replace STATE/BOARD/LOG in one rewrite.

Preferred direction:

1. Introduce Run as an orchestration layer over existing canonical truth.
2. Mirror current lifecycle into Run.
3. Prove restart/resume.
4. Move retry/failover ownership into Run.
5. Add typed waitpoints.
6. Add leases/queues.
7. Gradually reduce duplicated orchestration state.

Avoid a "new engine beside old engine forever" architecture.

There must eventually be one authority for each concept.

---

# COMPATIBILITY

Existing projects without Run records must remain recoverable.

Possible migration:

legacy execution_intent + STATE
-> synthesize/import RUN record
-> record migration evidence
-> continue

Do not fabricate historical attempt detail that did not exist.

Mark imported legacy history honestly.

---

# SECURITY

Durability must not weaken isolation.

Requirements:

- no secrets in Run records;
- account credentials remain provider-native / secure-store owned;
- waitpoint completion authorization is scoped;
- executor lease does not imply privilege escalation;
- replay cannot bypass irreversible-effect authorization;
- version pinning validates provenance;
- cross-user runtime remains least-privilege;
- machine runtime cannot be replaced by an untrusted writable user path.

---

# NON-GOALS

This Future Gate does not initially require:

- cloud hosting;
- Kubernetes;
- public SaaS;
- billing;
- autoscaling across internet machines;
- TypeScript SDK parity with Trigger.dev;
- cron UI;
- replacing Git;
- replacing SAIPEN lifecycle;
- forcing every project into distributed execution.

The first target is local durable autonomous execution.

---

# ACCEPTANCE — MASTER

The Future Gate may be considered mature when all are true:

1. `/goal` has durable Run identity.
2. Run survives model/process/host restart.
3. Current Work resumes from canonical checkpoint.
4. Work and Attempt are separate concepts.
5. executor incompatibility causes failover, not operator handback.
6. typed waitpoints own WAIT_USER/WAIT_EXTERNAL.
7. waiting releases executor capacity.
8. duplicate operations are idempotent.
9. irreversible effects are replay-safe or explicitly non-replayable.
10. runtime/protocol generation is pinned.
11. compatible runtime upgrade/migration is explicit.
12. completed valid sub-results can be reused.
13. trace graph explains Run history.
14. GUI consumes realtime machine metadata.
15. operator checkpoint remains compact.
16. cold recovery does not depend on chat/session history.
17. Windows reboot recovery is demonstrated.
18. provider/model replacement recovery is demonstrated.
19. canonical validation remains green.
20. no parallel competing orchestration authority remains.

---

# STRATEGIC END STATE

Today:

agent performs Work; SAIPEN preserves continuity.

Target:

SAIPEN owns a durable Run; compatible agents temporarily execute Attempts inside it.

The agent becomes replaceable compute.

The Run becomes the persistent unit of autonomy.
