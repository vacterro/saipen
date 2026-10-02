SAIPEN

# FUTURE GATE — VOLUNTARY MID-WORK CLAIM HANDOFF

STATUS: PROPOSAL / UPSTREAM PROTOCOL CAPABILITY GAP
PRIORITY: P2 RELIABILITY + OPERATOR UX
OWNER: SAIPEN protocol
SOURCE: observed live behavior during SAIMAIL T-5 continuation

## WHY THIS IS A FUTURE GATE, NOT AN AUDIT FAILURE

The current lease guard behaved correctly.

Observed behavior:

- T-5 was still owned by a previous `glm-5.3` host session.
- A new DeepSeek V4.1 Flash session attempted to continue the same T-5.
- `saipen claim T-5` refused with `TICKET_NOT_WORKABLE` because the foreign claim was still live.
- The protocol required waiting for the approximately 15-minute liveness lease to expire before takeover.

This is correct for an unexpected owner disappearance. A new process must not be able to steal a genuinely live ticket merely by claiming it.

The missing capability is a different case: the operator intentionally changes agents while work is still in progress.

Today both cases collapse into the same path:

```
old agent unexpectedly disappeared
        OR
operator intentionally switched agent
        -> foreign live claim
        -> wait for lease expiry
```

The second case should have a deliberate, evidenced, immediate transfer path without weakening the first case.

## REQUIRED INVARIANT

Default behavior MUST remain:

```
live foreign claim
-> generic takeover refused
-> stale takeover only after lease expiry
```

Add a separate operator/current-owner authorized path:

```
Agent A owns ticket T in phase P
-> explicit voluntary handoff
-> append-only handoff evidence
-> Agent A claim generation becomes non-authoritative
-> Agent B adopts SAME ticket T at SAME phase P
-> no lease wait
-> no DONE/CANCEL/restart side effect
```

The feature must not turn `saipen claim` into a claim-stealing primitive.

## PREFERRED UX

Prefer one atomic operation instead of a loose `release` followed by an unrelated `claim`:

```
saipen handoff T-5 --to deepseek-v4.1-flash
```

or equivalent canonical API operation.

A two-step API may exist internally, but the normal operator flow should avoid a race window between release and adoption.

Expected high-level result:

```
HANDOFF_PREPARED
from_owner: glm-5.3
from_session: <old session>
to_owner: deepseek-v4.1-flash
ticket: T-5
phase: SCOUT
claim_generation: N -> N+1
history: preserved
worktree: preserved
```

Then the new agent should be able to run:

```
saipen start
```

and resume the same ticket immediately.

## AUTHORITY TO HAND OFF

A voluntary handoff may be initiated only by one of:

1. the current canonical ticket owner/session; or
2. an explicit local operator action with authority to change execution ownership.

A random new agent must not be able to manufacture the handoff.

Do not infer operator approval merely because another model/session appeared.

## APPEND-ONLY EVIDENCE

Never rewrite the old claim as if it never existed.

Record a new event such as:

```
CLAIM_HANDOFF
TICKET: T-5
FROM_OWNER: glm-5.3
FROM_SESSION: ...
TO_OWNER: deepseek-v4.1-flash
FROM_PHASE: SCOUT
REASON: OPERATOR_AGENT_SWITCH
PREVIOUS_CLAIM_GENERATION: N
NEW_CLAIM_GENERATION: N+1
```

Exact schema is a protocol decision.

Required semantics:

- old claim remains historical evidence;
- ticket identity remains unchanged;
- phase remains unchanged unless an explicit transition is separately valid;
- already recorded evidence/checkpoints remain valid;
- no automatic rollback or replay;
- no synthetic DONE/CANCEL event;
- no fabricated timestamps or sessions.

## CLAIM GENERATION / FENCING

The transfer must create a new ownership generation or equivalent monotonic fence.

After successful handoff:

- canonical mutations from the previous ownership generation MUST be rejected;
- canonical mutations from the new owner MAY proceed;
- an old session waking up later must receive an explicit stale-owner result rather than silently mutating STATE/BOARD/LOG.

Example:

```
OLD_AGENT_MUTATION
-> REFUSE [STALE_CLAIM_GENERATION]
```

Do not reuse only wall-clock lease expiry as the fence after an explicit transfer.

## IMPORTANT LIMIT: RAW WORKTREE WRITES

SAIPEN ownership guards cannot by themselves stop an already-running external process from editing ordinary project files outside canonical SAIPEN mutation APIs.

Therefore distinguish two cases.

### Cooperative handoff

Preferred when Agent A is still responsive.

Agent A reaches a safe interruption point, acknowledges relinquishment, stops writing, then ownership transfers.

### Operator-forced handoff

Allowed only as an explicit operator action when the old process has been intentionally stopped or the operator accepts the risk.

The protocol should make the limitation visible rather than pretending metadata fencing can prevent arbitrary filesystem writes by a still-running process.

Do not weaken the ordinary live-claim guard to solve this.

## SAFE INTERRUPTION POINT

Investigate whether handoff should be allowed:

- at every phase; or
- only after a checkpoint / tool call boundary.

Desired user experience is genuine mid-work switching, including BUILD, but correctness outranks convenience.

If the implementation cannot prove the worktree is quiescent, the handoff operation should report that limitation explicitly.

Possible result:

```
HANDOFF_REQUIRES_QUIESCENCE
```

rather than waiting for the stale lease for no reason.

## RECOVERY SEMANTICS

Unexpected disappearance remains unchanged:

```
no explicit handoff
-> live lease protects current owner
-> lease expires
-> stale claim becomes adoptable
```

Explicit handoff path:

```
operator/current owner requests handoff
-> transfer evidence committed
-> old generation fenced
-> new owner can adopt immediately
```

If transfer is interrupted after old ownership is relinquished but before Agent B starts, the ticket must remain resumable and must not become DONE or lost.

## `saipen start` BEHAVIOR

After a completed voluntary handoff, `saipen start` in the target/new session should discover the transferred ticket and continue it automatically.

The operator should not need to manually manipulate:

- BOARD
- STATE
- LOG
- claim_session
- owner

The desired workflow is:

```
operator intentionally changes model
-> canonical handoff
-> new model: saipen start
-> exact same ticket continues
```

## REQUIRED TEST MATRIX

1. Live foreign claim + ordinary `claim` -> still REFUSE.
2. Live foreign claim + ordinary `start` from unrelated agent -> still WAIT/REFUSE.
3. Current owner voluntarily hands off -> immediate transfer succeeds.
4. Explicit operator-authorized handoff -> immediate transfer succeeds.
5. New agent continues same ticket id and same phase.
6. Old agent attempts canonical mutation after transfer -> refused as stale generation.
7. Existing checkpoints/evidence survive transfer byte-for-byte.
8. No DONE/CANCEL event is generated by handoff.
9. Handoff followed by new-agent crash -> ticket remains recoverable.
10. Two competing target agents cannot both adopt the transferred claim.
11. Replaying the same handoff request is idempotent or explicitly refused without duplicate ownership.
12. Stale-lease takeover still works when no explicit handoff exists.
13. A random agent cannot self-authorize handoff of another live owner.
14. Operator-forced handoff clearly records that it was forced.
15. No manual BOARD/STATE/LOG rewrite is necessary in the supported path.

## NON-GOALS

Do not solve this by:

- shortening the global lease to near-zero;
- allowing any new claimant to override a live owner;
- marking the ticket DONE and reopening it;
- creating a replacement ticket;
- deleting old claim history;
- treating model identity as authority;
- relying solely on timestamps without a monotonic claim-generation fence.

## ACCEPTANCE

This future gate is satisfied when an intentional agent/model switch can resume the same in-progress ticket immediately through a canonical, append-only, operator/current-owner-authorized handoff while preserving the existing protection against accidental concurrent ownership.

The 15-minute lease remains the failure-recovery mechanism, not the normal price of intentionally changing models.

## PROTOCOLIST QUESTIONS

The SAIPEN protocol owner should decide:

1. exact command/API name: `handoff`, `transfer`, or `release + adopt`;
2. whether transfer is atomic or staged;
3. how operator authorization is represented;
4. whether handoff is legal in every lifecycle phase;
5. whether cooperative acknowledgement is required when old owner is live;
6. exact stale-generation refusal code;
7. whether target owner must be named or may be `NEXT_AGENT` / unbound;
8. how `saipen start` discovers and adopts an explicitly transferred ticket;
9. how this interacts with continuation reservations and host-session liveness;
10. whether the feature belongs in the core claim state machine or a higher-level orchestration layer.

