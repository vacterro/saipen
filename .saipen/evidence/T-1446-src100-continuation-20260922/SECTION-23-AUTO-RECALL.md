23. MID-WORK AGENT REPLACEMENT — AUTO-RECALL + AUTO-KICK
NEW VERIFIED FIELD FAILURE
A real SAIFREN session demonstrated this sequence:

```
user issued:
    cc

SAIPEN correctly routed:
    saipen continue --json

convergence continued correctly:
    queued SRC-016
    crew
    PLAN
    T-181 claim
    SCOUT

the acting agent then read substantial project/source context

mid-work, the effective model/agent incarnation changed

the replacement agent reinterpreted the ORIGINAL user token:

    "cc"

as an ambiguous chat message and asked the user what it meant

```

This is a protocol continuity failure.
It is NOT a command-alias problem.
`cc` is already canonically defined as `saipen continue`.
It is NOT primarily a cold-recovery-data problem.
The current tree already has:

```
BOOT zero-context orientation
canonical STATE / BOARD / LOG
cold_route
context orient
cold_recovery recovery package
ACTIVE_WORK
PHASE
LAST_EVENT
NEXT_ACTION
NEXT_COMMAND
claim/session metadata
watchdog lease state

```

The missing invariant is:

```
A NEW AGENT INCARNATION ENTERING AN ALREADY ACTIVE EXECUTION MUST RECOVER
THE ACTIVE EXECUTION BEFORE IT IS ALLOWED TO INTERPRET OLD CHAT TEXT.

```

The user must never be the mechanism that notices this failure and types `cc`
again.
23.1 REQUIRED INVARIANT
Define and enforce one invariant:

```
ACTIVE EXECUTION OUTRANKS REINTERPRETATION OF HISTORICAL INGRESS.

```

If canonical state says that Work has already been:

```
projected
claimed
entered into an executable phase
and not terminally stopped

```

then a replacement agent must treat the current canonical execution state as
its immediate instruction.
It must NOT return to the original natural-language message and ask what the
message meant.
Examples:

```
user message:
    cc

canonical state:
    task: T-181
    phase: SCOUT
    next_action: PHASE SCOUT T-181

replacement behavior MUST be:
    recover T-181
    recover SCOUT context
    recover last durable checkpoint
    continue SCOUT

replacement behavior MUST NOT be:
    "cc is ambiguous"
    "what would you like me to do?"
    "should I continue?"
    "I can keep exploring if you want"

```

The same rule applies when the original ingress was:

```
cc
ccc
saipen continue
a natural-language task
a Source receipt
a goal/converge request

```

Once the request has been durably projected and execution has advanced beyond
ingress interpretation, historical ingress is evidence, not a new question.
23.2 DISTINGUISH USER INTERRUPT FROM AGENT REPLACEMENT
Do not solve this by blindly ignoring every new user message.
The system must distinguish:

```
HISTORICAL_INGRESS
NEW_USER_INTERRUPT
AGENT_REPLACEMENT

```

A genuinely newer user message still outranks execution under normal protocol
precedence.
But an agent replacement that merely receives/replays the same historical
message must not create a second ingress interpretation.
Use durable identity where available:

```
Source receipt identity
request digest
event id
ingress digest
host/session turn identity
persisted execution epoch
active Work identity

```

Do not use prose similarity alone.
Do not use model memory.
Do not use message timestamp alone when a stronger durable identity exists.
If the host cannot provide a stable message identity, use the already durable
Source/request digest plus current canonical execution epoch to prevent
re-interpretation of an ingress that has already been consumed.
23.3 ADD AN EXECUTION EPOCH / INCARNATION BOUNDARY
Introduce one DERIVED runtime identity for an active autonomous execution.
Conceptually:

```
execution_epoch
agent_incarnation
ingress_identity
active_work
phase
based_on_event
last_checkpoint
canonical_next_action

```

The execution epoch is NOT new protocol truth.
STATE / BOARD / LOG remain canonical.
The epoch exists only to answer:

```
"Is this agent continuing the execution already in progress, or is it
processing a genuinely new ingress?"

```

A model/provider/session replacement may change:

```
agent_incarnation

```

without changing:

```
execution_epoch

```

That is the normal mid-work replacement case.
The successor must inherit the active execution.
Do not create a new Work item merely because the model changed.
Do not re-run START merely because the model changed.
Do not re-project the same Source merely because the model changed.
23.4 AUTO-RECALL CAPSULE
Build one bounded machine-readable AUTO_RECALL projection from canonical truth.
Reuse `cold_recovery` / `context orient` machinery rather than creating a second
recovery authority.
At minimum expose:

```
project_root
saipen_home
execution_epoch
agent_incarnation
active_work
source_receipt
phase
last_event
last_durable_checkpoint
last_verified_slice
owner
claim_time
claim_session
claim_liveness
mutation_lease
blocker
blocker_scope
operator_action_due
parked_work
execution_intent
canonical_next_action
exact_resume_command
ingress_identity
ingress_already_consumed
replacement_detected

```

The capsule must contain an explicit machine directive equivalent to:

```
THIS IS AN ACTIVE CONTINUATION.
DO NOT REINTERPRET THE HISTORICAL USER INGRESS.
RECOVER CURRENT WORK AND EXECUTE THE EXACT RESUME ACTION NOW.

```

This is execution data, not conversational advice.
23.5 AUTO-KICK
AUTO_RECALL alone is insufficient.
A replacement agent can still read a perfect recovery object and then wander
off into chat.
Add AUTO_KICK at the strongest host-controlled boundary available.
On replacement / cold incarnation while active execution exists:

```
detect active execution
construct AUTO_RECALL
inject/bind it before free-form reasoning
run the canonical continuation entry automatically

```

Equivalent semantic action:

```
saipen continue --json

```

or, when the active phase route is already known and the protocol requires
direct phase continuation:

```
execute that canonical phase action

```

No human keystroke.
No:

```
"type cc again"

```

No:

```
"continue?"

```

No:

```
"what would you like me to do?"

```

No second interpretation round.
If the replacement occurs after a claim:

```
resume the claimed Work

```

If it occurs after a checkpoint:

```
resume from the checkpoint

```

If it occurs during an executable phase with no newer checkpoint:

```
reconstruct the smallest bounded phase context from canonical files and
continue from current truth

```

If a true WAIT / OPERATOR_ACTION_DUE exists:

```
AUTO_KICK stops there and surfaces that exact human action

```

If a safety/integrity refusal exists:

```
preserve the refusal

```

AUTO_KICK must never bypass a real human gate.
23.6 TURN-ENTRY GATE
Enforce a turn-entry ordering rule for SAIPEN-aware agents:

```
1. bind project
2. detect active execution / replacement state
3. recover canonical execution
4. resolve new-vs-historical ingress
5. execute canonical continuation
6. only then permit ordinary conversational interpretation

```

This ordering is mandatory.
The current failure happened because ordinary conversational interpretation was
allowed to run after canonical execution had already progressed.
The new rule must make that state unreachable.
A replacement model must not begin with:

```
"What did the user mean?"

```

when canonical truth already answers:

```
"What am I doing now?"

```

23.7 BOOT CONTRACT HARDENING
BOOT already says:

```
distrust your own memory
files outrank model memory
use zero-context orientation

```

Strengthen this from advisory prose into an executable admission invariant.
When:

```
active Work exists

```

and:

```
phase is executable

```

and:

```
no true operator gate / safety stop exists

```

then BOOT result must classify:

```
CONTINUATION_REQUIRED

```

and provide:

```
active_work
phase
based_on_event
exact_resume_command
ingress_identity
replacement_detected

```

A SAIPEN-aware host must not release the turn to ordinary free-form handling
before this admission has been consumed.
Do not rely on the model remembering to obey BOOT prose.
23.8 CONTINUE PAYLOAD HARDENING
The current route payload says approximately:

```
Routing is not completion evidence.
Read load_path.
Execute action in this turn.

```

Keep that, but add a stronger continuation contract when Work becomes active.
The route/result should explicitly expose fields equivalent to:

```
continuation_required: true

historical_ingress_consumed: true

active_work: T-###

resume_from:
    phase
    last_event
    checkpoint

replacement_policy:
    recover_then_execute

conversation_policy:
    do_not_reinterpret_consumed_ingress

canonical_next_command:
    ...

```

The public payload must make the correct behavior mechanically testable.
Do not hide this rule only inside an English instruction string.
23.9 CHECKPOINT MUST SUPPORT COGNITIVE RECONSTRUCTION
The current checkpoint/recovery data is strong but must be sufficient for a
completely unrelated successor model.
At every meaningful bounded slice, ensure recovery can reconstruct:

```
what Work is active
why it exists
what Source/request owns it
current phase
what has already been inspected
what has already been changed
what has already been verified
what remains
exact next bounded action
known non-goals
known expensive checks not to repeat

```

The replacement must not need the previous model's hidden reasoning.
It must not need conversational memory.
It must not need the human to summarize what happened.
This is the practical form of:

```
AGENT IS DISPOSABLE.
STATE IS NOT.

```

23.10 DO NOT CONFUSE ACTOR REPLACEMENT WITH WORK OWNERSHIP LOSS
A provider/model replacement may produce an entirely different LLM.
That alone must NOT mean:

```
active Work vanished
claim vanished
user intent vanished
Source vanished
phase reset
new PLAN required
new SCOUT required
user confirmation required

```

Separate:

```
logical SAIPEN seat / execution ownership

```

from:

```
physical model instance / provider incarnation

```

If the same legal execution seat is being continued by a replacement model,
recover the seat.
Only canonical authority conflict may refuse adoption.
23.11 HOST-ADAPTER BOUNDARY
Inspect the actual SAIFREN / host integration path used to launch and replace
agents.
Prefer an enforceable host/session-start hook over prompt-only instructions.
The strongest acceptable implementation is:

```
replacement detected by host/runtime
    ->
canonical AUTO_RECALL obtained
    ->
recovery capsule injected
    ->
AUTO_KICK continuation executed
    ->
agent receives active Work context

```

If SAIPEN currently has no hook capable of running before replacement-agent
free-form reasoning:

```
do not pretend a BOOT.md wording change guarantees the requirement

```

Instead:

```
implement everything possible in the protocol/runtime
expose one exact adapter contract
classify the remaining host seam explicitly
add a deterministic adapter test/harness
keep T-1446 open until the real SAIFREN path demonstrates the behavior

```

"Prompt tells the model to continue" is not acceptance.
23.12 MID-WORK REPLACEMENT ACCEPTANCE TEST
Add one deterministic regression matching the observed failure.
Scenario:

```
user ingress:
    cc

continuation routes successfully

queued Source is projected

crew/planner advances

T-X is claimed

phase enters SCOUT or BUILD

checkpoint exists

model/agent incarnation A disappears

incarnation B starts with zero private memory

B receives the historical conversation tail containing the original `cc`

```

Expected:

```
B first resolves the active continuation

B identifies T-X

B identifies current phase

B identifies last durable checkpoint

B identifies exact next action

B does NOT ask what `cc` means

B does NOT call START for the consumed ingress

B does NOT create duplicate Source

B does NOT create duplicate Work

B does NOT reset phase

B does NOT require human interaction

B continues useful bounded work

```

Required counters:

```
manual_continue_count = 0
duplicate_source_count = 0
duplicate_work_count = 0
ingress_reinterpretation_count = 0
lost_claim_count = 0
phase_reset_count = 0

```

23.13 HOSTILE REPLACEMENT MATRIX
Test replacement at multiple boundaries:

```
after `saipen continue --json`
after Source projection
after crew role completion
after PLAN
immediately after claim
mid-SCOUT
mid-BUILD
after file reads
after first mutation
after checkpoint
mid-VERIFY
after VERIFY before REVIEW
mid-REVIEW

```

For every executable case:

```
zero manual `cc`

```

For legitimate WAIT cases:

```
exactly the real operator action is surfaced

```

For safety/refusal cases:

```
fail closed

```

Also test replacement with:

```
same model / new context
different model / same provider
different provider
context-compacted session
completely cold session

```

Model identity must not alter the canonical outcome.
23.14 HISTORICAL `cc` RED CONTROL
Create an explicit red control for the exact anti-pattern:

```
active claimed Work exists
successor sees old `cc`
successor treats `cc` as ambiguous natural language

```

That control must FAIL.
Equivalent forbidden result classes include:

```
ASK_USER_MEANING
REQUEST_CLARIFICATION
IDLE_CHAT
REINTERPRET_CONSUMED_INGRESS

```

when:

```
continuation_required == true
operator_action_due == false

```

A future regression must therefore become mechanically visible rather than
showing up eleven minutes into a SAIFREN run.
23.15 AUTONOMY RELATION
This requirement belongs directly to T-1446 / SRC-100.
Do not create another broad autonomy umbrella.
The autonomous supervisor work is incomplete unless it survives:

```
worker process death

```

AND:

```
cognitive/model incarnation replacement

```

These are different failures.
Worker turnover proves process continuity.
AUTO_RECALL + AUTO_KICK must prove cognitive execution continuity.
T-1446 cannot close while replacing the LLM mid-work can turn:

```
"continue the claimed ticket"

```

into:

```
"what did you mean by cc?"

```

23.16 ADD TO T-1446 TERMINAL CONDITIONS
Extend T-1446 closure requirements with:

```
mid-work agent replacement recovery PASS

historical ingress reinterpretation count = 0

manual re-kick count = 0

duplicate Source after replacement = 0

duplicate Work after replacement = 0

active claim survives legal incarnation replacement

active phase survives legal incarnation replacement

successor reconstructs current Work without predecessor private memory

exact continuation happens before free-form reinterpretation

real SAIFREN replacement path demonstrated when that host seam is available

```

Prompt-only compliance is insufficient.
23.17 ADD TO FINAL REPORT
Add:

```
AUTO_RECALL STATUS

AUTO_KICK STATUS

TURN-ENTRY GATE STATUS

AGENT REPLACEMENT TEST STATUS

REAL SAIFREN REPLACEMENT STATUS

HISTORICAL INGRESS REINTERPRETATION COUNT

MANUAL RE-KICK COUNT

DUPLICATE SOURCE AFTER REPLACEMENT COUNT

DUPLICATE WORK AFTER REPLACEMENT COUNT

LOST CLAIM AFTER REPLACEMENT COUNT

PHASE RESET AFTER REPLACEMENT COUNT

REPLACEMENT RECOVERY LATENCY

```

Required zero values:

```
HISTORICAL INGRESS REINTERPRETATION COUNT
MANUAL RE-KICK COUNT
DUPLICATE SOURCE AFTER REPLACEMENT COUNT
DUPLICATE WORK AFTER REPLACEMENT COUNT
LOST CLAIM AFTER REPLACEMENT COUNT
PHASE RESET AFTER REPLACEMENT COUNT

```

The final invariant is:

```
A HUMAN STARTS THE WORK ONCE.

A MODEL MAY DIE, DISAPPEAR, COMPACT, OR BE REPLACED.

SAIPEN REMEMBERS WHAT THE SYSTEM IS DOING AND KICKS THE SUCCESSOR BACK INTO
THE ACTIVE EXECUTION WITHOUT ASKING THE HUMAN TO REPEAT HIMSELF.

```
