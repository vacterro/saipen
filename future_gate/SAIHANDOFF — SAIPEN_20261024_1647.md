
SAIHANDOFF — SAIPEN FUTURE GATE REGISTRATION
TITLE: Architectural Simplification and Causal Self-Recovery
TYPE: DEFERRED ARCHITECTURE CAMPAIGN
PRIORITY: P1
TARGET: SAIPEN
EXECUTION MODE: RECORD ONLY
IMPLEMENTATION AUTHORITY: NOT GRANTED
AUTO-PROMOTION: NOT AUTHORIZED

============================================================
1. MISSION
============================================================

Register a long-term architectural improvement campaign in SAIPEN's canonical Future Gate system.

Do not implement the architecture now.

The purpose is to preserve an important architectural direction for later deliberate activation, without losing its rationale, failure examples, technical constraints or proposed engineering workstreams.

Future campaign name:

ARCHITECTURAL SIMPLIFICATION AND CAUSAL SELF-RECOVERY

Core objective:

Replace the growing collection of incident-specific refusal rules, fallback loops and manual recovery requirements with a smaller set of enforceable system invariants, causal ownership relationships, typed lifecycle facts and mechanically provable recovery operations.

SAIPEN should not need a separate hardcoded workaround for every new agent mistake.

It should detect unfamiliar but structurally recognizable failures, reason over canonical evidence and recover automatically when safety can be proven.

The system must remain secure even when its executing AI model makes incorrect assumptions or proposes invalid state changes.

============================================================
2. REGISTRATION CONTRACT
============================================================

Canonical rule owner:

saipen/FUTURE.md
FUTURE-GATE-01

Canonical CLI:

saipen future add
saipen future refresh
saipen future status
saipen future list

Canonical implementation:

tools/saipen_engine/future_gate.py

Canonical storage:

future_gate/
.saipen/future/index.json

This is an explicit operator-requested DEFERRED architecture candidate.

Before registration:

1. Inspect the current Future Gate corpus and index.
2. Search for an existing gate with the same architectural scope.
3. Distinguish historical narrow reconciliation incidents from the proposed system-wide architectural redesign.
4. Reuse an equivalent gate when one already exists.
5. Do not create duplicate gates.
6. Preserve existing historical Future Gate documents.
7. Record the new gate only if its architectural scope is not already represented.

Use the canonical future-add operation when creating a new gate.

Suggested command shape:

saipen future add "Architectural Simplification and Causal Self-Recovery" --priority P1 --body "<full architecture proposal>"

Replace the body placeholder with the complete proposal recorded below.

The resulting document must use the canonical machine-readable Future Gate format.

Required properties:

state: DEFERRED
priority: P1
basis: reproduced
needs: none
slice: TODO -- define one bounded implementation slice only when the future campaign is deliberately activated

Important:

The exact TODO -- placeholder is intentional.

It prevents the Future Gate readiness machinery from automatically considering this broad architectural idea ELIGIBLE.

Do not assign a ready-to-promote slice now.

Do not invoke saipen future promote.

Do not create ordinary Work, a new active goal or an implementation ticket.

Do not treat gate registration as permission to modify production architecture.

Use existing repository evidence paths where available, including:

tools/saipen_engine/reconcile.py
tools/test_recovery_reachability.py
.saipen/evidence/T-1864-autonomous-valve/README.md
.saipen/evidence/T-1566-reconciliation/reconciliation.md

These paths support the recorded context. They do not prove the entire proposed architecture.

============================================================
3. ARCHITECTURAL PROBLEM STATEMENT
============================================================

SAIPEN currently contains multiple mechanisms for:

- Execution authority.
- Source provenance.
- Goal continuation.
- Safety valves.
- Recovery.
- Reconciliation.
- Phase transitions.
- Work ownership.
- Blocking decisions.
- External gates.
- Journal verification.
- Auto-Doctor behavior.

These mechanisms protect legitimate boundaries, but their composition can produce recurring execution deadlocks.

Observed failure class:

1. An AI model performs an invalid or unsupported operation.
2. Canonical state becomes inconsistent or contains an unsupported blocker.
3. SAIPEN correctly detects uncertainty.
4. Reconciliation cannot distinguish a recoverable technical inconsistency from a genuine authorization requirement.
5. A conservative global refusal prevents further execution.
6. The user is asked to perform manual recovery.
7. A narrow workaround is introduced.
8. A structurally similar problem later appears through another route.

The architectural problem is not that SAIPEN lacks enough individual rules.

The problem is that prevention, causal diagnosis and automatic recovery are not yet sufficiently unified around enforceable invariants.

The target is to reduce entire classes of failures rather than accumulate increasingly specialized recovery recipes.

============================================================
4. FUTURE WORKSTREAM A — TYPED CANONICAL STATE
============================================================

Replace reliance on freeform structural blocker strings with typed, verifiable facts.

Every authoritative blocker should carry sufficient information to establish:

- Blocker identity.
- Owning component.
- Owning ticket or goal.
- Affected project.
- Lifecycle phase.
- Causal source.
- Source event.
- Authority requirement.
- Scope.
- Relevant dependencies.
- Conditions for resolution.
- Expiration or invalidation semantics.
- Recovery classification.

The executing model must not acquire the ability to create an authoritative security gate merely by writing explanatory prose into STATE.

Separate:

DIAGNOSTIC_TEXT
CANONICAL_BLOCKER
AUTHORITY_GATE
EXTERNAL_DEPENDENCY
RECOVERABLE_INCONSISTENCY

Avoid creating multiple competing sources of truth.

The canonical journal and typed lifecycle operations must remain authoritative.

============================================================
5. FUTURE WORKSTREAM B — CAUSAL DEPENDENCY GRAPH
============================================================

Introduce or consolidate a causal relationship model connecting:

- Goals.
- Tickets.
- Sources.
- Journal events.
- State transitions.
- Dependencies.
- Verification records.
- Publication gates.
- Blockers.
- Operator decisions.

The presence of an unrelated BLOCKED ticket must not influence a separate active task without a proven dependency relationship.

Required invariant:

Adding an unrelated blocked ticket cannot change authorization or recovery eligibility for another independent task.

Do not infer causality from ticket proximity, freeform prose similarity or global BOARD membership.

When relationships are unknown, preserve the genuine uncertainty locally instead of globally freezing unrelated execution.

The graph should derive from existing canonical records wherever possible.

Avoid creating a redundant mutable graph database that can diverge from the journal.

============================================================
6. FUTURE WORKSTREAM C — INVARIANT-DRIVEN AUTO-DOCTOR
============================================================

Develop a recovery mechanism driven by system invariants rather than an ever-growing list of narrowly matched incident strings.

Proposed diagnostic cycle:

DETECT
-> COLLECT CANONICAL FACTS
-> IDENTIFY VIOLATED INVARIANTS
-> ESTABLISH CAUSAL SCOPE
-> CLASSIFY RECOVERABILITY
-> GENERATE MINIMAL REPAIR PLAN
-> VERIFY SAFETY
-> APPLY CANONICALLY
-> RECHECK
-> RESUME

Possible repair classes:

- Stale derived STATE projection.
- Inconsistent next_action.
- Orphaned non-authoritative blocker.
- Reconciled but unreflected journal transition.
- Recoverable process or launcher mismatch.
- Obsolete dependency reference.
- Completed recovery operation requiring idempotent finalization.
- Temporary infrastructure failure with a safe retry policy.

Do not automatically repair:

- Missing independent operator authority.
- Revoked permissions.
- Unauthorized publication.
- Unknown destructive effects.
- Unverified external decisions.
- Irrecoverable journal conflicts.
- Security-significant source ambiguity.

Recovery must be based on proof, never optimism.

============================================================
7. FUTURE WORKSTREAM D — TRANSACTIONAL STATE API
============================================================

Consolidate structural mutations behind canonical operations.

The executing model proposes intent.

The kernel validates and applies the state transition.

Required properties:

- Typed operation input.
- Preconditions.
- Current revision binding.
- Ownership validation.
- Authority validation.
- Atomic mutation.
- Durable journal entry.
- Idempotency.
- Compare-and-swap protection.
- Crash recovery.
- Postcondition verification.

Prevent direct accidental structural mutation from becoming authoritative merely because a file was written.

Retain legitimate recovery tooling for corrupted or historical projects.

Do not rewrite the entire persistence system without proving the need.

============================================================
8. FUTURE WORKSTREAM E — FAST PATH AND RECOVERY PATH
============================================================

Architecturally separate ordinary execution from exceptional recovery.

FAST PATH

Used when:

- State is consistent.
- Authority is valid.
- Ownership is established.
- Dependencies are satisfied.
- The next operation is permitted.

Behavior:

Perform the minimal necessary checks and execute efficiently.

RECOVERY PATH

Used when:

- Canonical facts contradict.
- A transition is incomplete.
- A blocker lacks causal ownership.
- Journal/state projections disagree.
- Runtime identity is uncertain.
- A recoverable infrastructure error appears.

Behavior:

Run bounded causal diagnosis and verified recovery.

Do not rerun expensive recovery analysis on every healthy command.

Do not repeatedly execute a failed repair without changed evidence.

The fast path should become simpler as the recovery architecture matures.

============================================================
9. FUTURE WORKSTREAM F — PROPERTY-BASED AND METAMORPHIC TESTING
============================================================

Build tests that discover entire classes of logical failures.

Required invariants include:

F01. Adding unrelated BLOCKED tickets does not alter the current task's independent authorization.

F02. Reordering unrelated BOARD entries does not change canonical decisions.

F03. Repeated recovery is idempotent.

F04. A journaled transition survives restart without duplicated effects.

F05. A stale STATE projection cannot silently override verified journal truth.

F06. A model-authored string cannot grant operator authority.

F07. A model-authored string cannot invent an authoritative gate.

F08. An unrelated external blocker cannot freeze independent authorized work.

F09. Valid persistent authority survives ordinary checkpoints.

F10. Invalid or expired authority remains invalid after recovery.

F11. Recovery never creates new authorization.

F12. A failed repair leaves the previous canonical state recoverable.

F13. An interrupted operation cannot fabricate a completed publication.

F14. Different equivalent representations of the same canonical facts produce the same authorization decision.

F15. Introducing an independent ticket does not change a completed ticket's historical result.

F16. Restarting the host does not change the scope of existing valid authority.

F17. A stale diagnostic message cannot override the current canonical next action.

F18. A blocked operation does not prevent unrelated permitted operations.

F19. Recovery does not rewrite immutable forensic evidence.

F20. Independent concurrent readers cannot create contradictory state mutations.

Use generated state combinations and controlled fault injection.

Preserve deterministic seeds for reproducibility.

Property-based tests complement, rather than replace, the existing integration and end-to-end suites.

============================================================
10. FUTURE WORKSTREAM G — ARCHITECTURAL SIMPLIFICATION
============================================================

Investigate whether existing mechanisms can be consolidated safely.

Potential targets:

tools/saipen_engine/reconcile.py
tools/saipen_engine/operations.py
tools/saipen_engine/goal_authority.py
tools/saipen_engine/router.py
tools/saipen_engine/continue_loop.py
tools/saipen_engine/board.py
tools/saipen_engine/journal.py
tools/saipen_engine/conformance.py

Look for:

- Duplicate blocker classification.
- Repeated source authority checks.
- Competing lifecycle decision rules.
- Overlapping recovery implementations.
- Recursive fallback behavior.
- Multiple incompatible status contracts.
- Redundant parsing and normalization.
- Repeated full-state inspection.
- Legacy workaround branches.
- Unnecessary coupling between projects and phases.

Prefer replacing demonstrably duplicated mechanisms with one verified canonical implementation.

Do not perform speculative mass refactoring.

Any future implementation must measure whether complexity, correctness and execution cost actually improve.

============================================================
11. REQUIRED ARCHITECTURAL CONSTRAINTS
============================================================

The future campaign must preserve:

- Independent operator-origin verification.
- Source authority.
- Single-writer discipline.
- Journal integrity.
- Canonical ownership.
- Existing security boundaries.
- Idempotent recovery.
- Legitimate publication gates.
- Crash consistency.
- Verification fidelity.
- External dependency truth.
- Cross-project isolation.
- Existing valid user decisions.
- Historical evidence.
- Backward compatibility where required.

No fail-open authorization behavior.

Fail-open execution is permitted only where the action is independently authorized and the failure does not compromise safety or correctness.

Do not replace a deadlock with silent privilege escalation.

============================================================
12. FUTURE ACTIVATION STRATEGY
============================================================

When the operator deliberately activates this architecture campaign in the future:

1. Review the current architecture, not the historical snapshot alone.
2. Revalidate every historical failure example.
3. Identify which root causes have already been repaired.
4. Identify the remaining architectural gaps.
5. Prepare an architecture decision record.
6. Establish a compatibility and migration strategy.
7. Select ONE bounded implementation slice.
8. Attach real current evidence.
9. Use canonical Future Gate readiness and promotion.
10. Implement incrementally with regression controls.

Candidate first bounded slice:

Establish a typed causal blocker classification layer for reconciliation, preserving all existing security boundaries.

This is an architectural suggestion only.

It must NOT become an executable slice during the current registration request.

Other workstreams remain deferred until separately reviewed.

Do not automatically schedule the full redesign.

============================================================
13. DUPLICATE AND OWNERSHIP SAFETY
============================================================

Existing narrow recovery tickets or historical gates may overlap with parts of this proposal.

Do not reopen them.

Do not mark them obsolete merely because a broader architecture proposal exists.

Do not declare previously implemented functionality absent without checking current code.

This Future Gate owns the long-term architecture direction only.

Active defects retain their existing Work owners.

The gate must not compete with ongoing repairs.

The proposed architecture must not become a second SAIPEN execution protocol.

============================================================
14. REGISTRATION VERIFICATION
============================================================

After creating or updating the deferred gate:

V01. Verify the document exists in future_gate/.

V02. Verify its machine header is valid.

V03. Verify its assigned FG identity is unique.

V04. Verify the document contains the complete architectural intent.

V05. Verify its lifecycle remains DEFERRED.

V06. Verify no executable bounded slice was declared.

V07. Verify it is not ELIGIBLE.

V08. Verify no promotion occurred.

V09. Verify no new active Work was created.

V10. Verify active STATE/BOARD execution is unchanged.

V11. Verify the index reflects the new or updated document.

V12. Verify existing future gates remain intact.

V13. Verify evidence references are valid or explicitly marked as historical context.

V14. Verify no production architecture was modified.

V15. Verify that the operator can locate this gate later by its assigned FG identifier and title.

Use canonical index refresh when necessary.

Do not hand-edit .saipen/future/index.json.

============================================================
15. FINAL RESPONSE
============================================================

Report only:

STATUS: FUTURE_GATE_RECORDED or EXISTING_GATE_UPDATED or BLOCKED
GATE_ID: actual canonical FG identifier
TITLE: Architectural Simplification and Causal Self-Recovery
STATE: DEFERRED
ELIGIBLE: false
PROMOTED: false
WORK_CREATED: false
DOCUMENT: actual repository-relative path
EVIDENCE: registration and index verification
NEXT_ACTION: NONE

If registration failed, report the exact error and the safe canonical recovery action.

Do not claim that the gate exists without verifying it.

============================================================
16. FINAL DIRECTIVE
============================================================

REGISTER THE ARCHITECTURAL IDEA.

PRESERVE THE COMPLETE DESIGN.

DO NOT IMPLEMENT IT NOW.

DO NOT PROMOTE IT.

DO NOT CREATE ACTIVE WORK.

DO NOT MODIFY THE EXECUTION ENGINE.

DO NOT CHANGE OPERATOR AUTHORITY.

This request is complete when the architectural proposal is durably recorded as a deferred Future Gate and its identity and state have been verified.

The future implementation campaign requires a separate deliberate activation.
