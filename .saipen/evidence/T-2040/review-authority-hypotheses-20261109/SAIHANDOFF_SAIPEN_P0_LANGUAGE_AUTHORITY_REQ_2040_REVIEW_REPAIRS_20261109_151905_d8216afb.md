# SAIHANDOFF — SAIPEN P0 LANGUAGE AUTHORITY / REQUEST ROUTING / T-2040 REVIEW REPAIRS

**MODE:** AUTONOMOUS FORENSIC / REPAIR / VERIFY / CONTINUE  
**PRIORITY:** P0  
**SOURCE:** SAIPEN_09.11.26-T13-06-04.zip  
**SNAPSHOT EVENT:** E-20788  
**CURRENT:** T-2040 / BUILD

## MISSION

Fix the confirmed language-contract conflict, preserve correct request handling when a project has active work, and complete the remaining T-2040 input-boundary repairs.

Avoid creating another umbrella ticket. Reconcile the current canonical state and reuse existing work wherever possible.

## 1. CONFIRMED LANGUAGE-CONTRACT CONFLICT

File: `saipen/STYLE.md`

Current setting:

`reply_language: et`

This explicitly forces Estonian for every chat response, regardless of user language.

File: `tools/saipen_engine/chat_style.py`

`contract_summary()` generates a host-facing instruction that repeats the forced Estonian language pin.

The same generated context states that higher-priority host instructions retain precedence.

A captured Freebuff/DeepSeek session displays both:

- SAIPEN: reply language pinned to Estonian.
- CLAUDE.md: respond in Russian.

The agent spends reasoning on the apparent authority conflict.

### REQUIRED FIX

1. Make Russian the intended default reply language for this installation.
2. Change the authoritative configuration to `reply_language: ru`.
3. Ensure all generated host instructions derive from the same selected contract.
4. Do not duplicate language rules independently in Claude, Freebuff, OpenCode, Gemini or other host adapters.
5. Detect contradictions between the effective host instruction and SAIPEN language configuration.
6. Report effective language and its authoritative source through machine-readable diagnostics.
7. Preserve the actual higher-priority instruction hierarchy.
8. Never silently treat an explicitly conflicting language instruction as compatible.
9. Keep protocol fields, code, paths, logs and machine-readable evidence unchanged.

### CRITICAL STYLE MIGRATION

The existing snapshot STATE carries:

`style_contract: ded-069a4c52`

The token is derived from STYLE.md content.

Changing the language also changes this token, potentially making existing project checkpoints stale.

Do not merely edit STYLE.md and globally replace STATE markers.

Implement or use a canonical, reversible style-contract migration that:

- Verifies current installation identity.
- Preserves historical checkpoint provenance.
- Updates required references using legitimate ownership operations.
- Does not discard active Work.
- Does not falsely certify an unread or invalid STATE.
- Supports a safe restart after the configuration change.
- Preserves pending operator decisions.
- Fails closed if migration cannot be completed safely.

Test the migration on an isolated project copy before applying it to the running installation.

## 2. REQUEST ROUTING IN ACTIVE PROJECTS

Captured BZDECOMP behavior:

- User asks for log-based investigation of a Hunt–Destroy FPS collapse.
- Agent invokes `saipen start`.
- Existing project STATE identifies T-786 / SCOUT.
- Agent subsequently inspects STATE.

This screenshot alone does not prove a deadlock or dropped request.

### REQUIRED VERIFICATION

Inspect the real `saipen start` result envelope.

Distinguish:

- STARTED: new Work acquired execution ownership.
- USER_REQUEST_RECORDED: new Work queued while existing Work retains its seat.
- Explicit authorized preemption.
- Foreign ownership.
- Invalid canonical state.
- Refused or incomplete request capture.

Ensure each result has a visible and durable disposition.

A new user request must not disappear because unrelated work was active.

When the request is queued, preserve:
- Exact captured user request.
- Source receipt.
- Work identity.
- Existing active ticket.
- Queue position and dependency state.
- Next executable action.

When current user input legitimately preempts existing work, preserve the interrupted ticket's exact phase and resume point.

Never preempt foreign-owned work or bypass authority restrictions.

Do not invent a deadlock if the agent is simply executing SCOUT.

Test active-task ingress and restart recovery across Freebuff, Claude and OpenCode-compatible adapters.

## 3. T-2040 REMAINING P0 DEFECTS

Canonical snapshot:

- Phase: BUILD.
- Ticket: T-2040.
- Last event: E-20788.
- BUILD resumed after VERIFY identified two new input-boundary defects.

### P0-A — Standing maintenance grant invalidation

The latest log reports that admission persists ACTIONABLE_GAPS and invalidates an otherwise unchanged standing grant.

Inspect:

- `tools/saipen_engine/goal_authority.py`
- `tools/saipen_engine/persistent_goal.py`
- `tools/saipen_engine/replenishment.py`
- `tools/saipen_engine/board.py`
- The actual goal admission and persistence path.

Establish the exact before/after grant identity and policy digest.

Separate mutable discovery and observation fields from security-relevant policy fields.

Required property:

Unchanged authenticated policy plus ordinary observation update must not revoke an otherwise valid standing grant.

Conversely, a genuine policy or authority change must still invalidate the grant.

Do not weaken the authorization boundary to make the test pass.

### P0-B — Malformed collect hypothesis crash

File:
`tools/saipen_engine/subs.py`

Function:
`_collect_hypotheses_problem()`

Current code around line 4149 constructs a hash set using tuples of raw hypothesis values.

Nested unhashable values can raise TypeError.

Replace this with safe structural validation and exact canonical identity comparison.

Requirements:

- Malformed nested input returns a structured invalid-evidence result.
- No exception escapes the collect admission boundary.
- Duplicates are detected deterministically.
- Contradictory package generations are rejected.
- Exact producer/source/revision bindings remain enforced.
- No forged collect receipt is accepted.
- Valid historical packages remain compatible where contractually allowed.

Add regression cases for nested list, dictionary, null, numeric, duplicate and contradictory hypothesis values.

## 4. CONTINUE T-2040

Review existing evidence before implementing fixes.

Relevant history:

- E-20781: 199 tests and 178 subtests PASS.
- E-20782: REVIEW identified malformed input guards.
- E-20784: bounded corrections recorded.
- E-20785: transition to VERIFY.
- E-20786/E-20787: measured regression FAIL then PASS.
- E-20788: new defects reproduced and BUILD resumed.

Preserve verified corrections from the earlier wave.

After new fixes:

1. Run red controls against the original affected implementation.
2. Run identical controls against the repaired implementation.
3. Run adjacent regression families.
4. Run the full relevant T-2040 suite.
5. Obtain fresh canonical validation.
6. Perform independent REVIEW.
7. Close T-2040 only if actual closure gates pass.
8. Continue to T-2042 and T-2041 when eligible.

T-2043 is already queued as a continuation request. Reconcile its overlap with T-2040 before generating further Work.

## 5. BZDECOMP PERFORMANCE INVESTIGATION BOUNDARY

The screenshot refers to a different project:

`V:\___VAC\__K\__CODE\_MISC\BZDECOMP`

Observed user symptom:

Hunt–Destroy applied to 30+ units reportedly reduces FPS to approximately 1–2.

The provided SAIPEN archive does not contain the relevant live BZDECOMP diagnostic trace.

Do not claim a performance root cause from unrelated SAIPEN logs.

When operating in BZDECOMP with its actual source and runtime evidence, investigate:

- Hunt–Destroy order dispatch.
- AI target-selection cost.
- Navigation/pathfinding frequency.
- Collision and unit avoidance.
- Repeated destination recalculation.
- Command propagation among large groups.
- Synchronous loops on the simulation thread.
- Allocation, logging and lock contention.
- Per-tick cost as unit count increases.

Capture reproducible frame/tick timing for 1, 10, 20 and 30+ selected units.

Compare idle, movement, attack and Hunt–Destroy states.

Distinguish CPU simulation slowdown from GPU rendering slowdown using actual measurements.

Any optimization must preserve unit orders, legitimate AI behavior and deterministic simulation requirements.

Do not mutate BZDECOMP merely because this SAIPEN handoff mentions it. Require the correct project binding, evidence and authority.

## 6. ACCEPTANCE CRITERIA

- Russian language selected without contradictory host instructions.
- STYLE migration does not corrupt active project checkpoints.
- Existing jobs survive a host restart.
- New requests are durably captured and correctly queued or executed.
- Active work is not silently overwritten.
- No false claims of deadlock.
- Standing grants survive harmless observation updates.
- Real authority-policy changes still invalidate grants.
- Malformed collect hypotheses fail closed without exceptions.
- T-2040 regressions pass independent verification.
- Canonical validation passes before final closure.
- No unauthorized Git, release or foreign-project mutations.

Ordinary tests must not disturb Windows foreground focus, keyboard, mouse or active desktop windows.

## 7. REQUIRED FINAL REPORT

STATUS:
CURRENT_TICKET:
LANGUAGE_ROOT_CAUSE:
EFFECTIVE_LANGUAGE:
STYLE_MIGRATION:
REQUEST_ROUTING:
T2040_REPAIRS:
REGRESSION_BEFORE:
REGRESSION_AFTER:
CANONICAL_VALIDATION:
BOARD:
AUTHORITY:
REMAINING_BLOCKERS:
NEXT_EXACT_ACTION:

Continue automatically through authorized work. Preserve real authority gates and source provenance.

Do not substitute a green test summary for a completed canonical lifecycle.

END SAIHANDOFF
