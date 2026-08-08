# SAIPEN v9 Runtime Design — Resident Execution Under SAIPEN Law

Status: RESEARCH / DESIGN ONLY. No runtime code is implemented by this document.
The v9 research gate (BOARD T-575) must open before any V9-M1 implementation.

Upstream studied: Prime Agent
  repo:   https://github.com/PrimeIntellect-ai/prime-agent
  commit: a18809e00ea30638584d87b3afea7285a9d7296c (2026-08-07)
  license: MIT (Copyright 2025 Mario Zechner)
  checkout: isolated at a research/reference location; never vendored.

Full per-mechanism extraction audit: `PRIME_AGENT_EXTRACTION.md` (same dir).
Machine-readable provenance: `saipen/runtime/UPSTREAM.json`.
Third-party notices: `THIRD_PARTY_NOTICES.md`.

---

## 0. The one-sentence thesis

SAIPEN owns truth, state, work, evidence, transitions, safety, freshness,
tickets, HUNT/CLEAN, Improve, and SubSaipen contracts; v9 runtime owns process
lifetime, resident sessions, queues, timers, scheduling, model connections,
detachable execution, runtime messaging, and optional computational scratch.
Runtime is machinery. SAIPEN remains law.

```
PRIME-STYLE RUNTIME MECHANICS
            +
    SAIPEN GOVERNANCE
```

not "SAIPEN replaced by Prime Agent".

## 1. Ownership boundary (hard)

Runtime (future `saipen/runtime/`, working name SAIRUNTIME) MAY own:

- resident Core session process;
- process ownership and supervision;
- queue, schedules, timers;
- heartbeat and continuation policy;
- detach/reattach and crash recovery;
- runtime event transport;
- SubSaipen process handles;
- optional scratch state (SAIREPL);
- runtime configuration and durable runtime records.

Runtime MUST NOT own:

- canonical BOARD;
- canonical STATE meaning;
- canonical LOG semantics;
- ticket selection policy;
- phase transitions;
- DONE decision;
- HUNT result truth;
- Improve acceptance;
- main-tree write authority.

Those remain Core protocol responsibilities. Runtime-owned durable records are
explicitly classified (section 8) and never merged with canonical state.

## 2. Conceptual ownership

| Concern | Owner |
|---|---|
| truth, state, work, evidence, transitions, safety | SAIPEN Core |
| freshness, tickets, HUNT/CLEAN, Improve | SAIPEN Core |
| SubSaipen contracts (charter, OUTBOX, freshness) | SAIPEN Core |
| process lifetime, resident sessions | v9 runtime |
| queues, timers, scheduling | v9 runtime |
| model connections, detachable execution | v9 runtime |
| runtime messaging, optional scratch state | v9 runtime |

## 3. Process architecture

Adopt the useful Prime Agent ownership shape; implement Windows-first with
Python stdlib only.

```
+-------------------+
|   SAIPEN CLIENT   |   CLI / SAIPENVIEW — presentation/input only.
+---------+---------+   Never owns execution.
          |
          v
+-------------------+
|    SUPERVISOR     |   one instance; process discovery; routing; attachment;
+---------+---------+   health; recovery; message delivery; queue/schedule owner.
          |
          v
+---------------------------+
| PROJECT RUNTIME           |   one root execution family per project.
| Core Session              |
| Queue                     |
| Scheduler / Heartbeats    |
| Continuation Policy       |
| SAIREPL (optional)        |
| SubSaipen Runtime Registry|
+-------------+-------------+
              |
    +---------+---------+
    |                   |
    v                   v
SubSaipen A         SubSaipen B
own context         own context
own workspace       own workspace
    |                   |
    +---------+---------+
              |
              v
          OUTBOX          (semantic handoff, unchanged)
              |
              v
           CORE           (the only path to canonical mutation)
              |
              v
 canonical repository: STATE / BOARD / LOG / KNOWLEDGE
```

Invariants:

- closing the client (SAIPENVIEW or CLI) does not stop active work unless the
  user explicitly requested stop (red control 1);
- client crash != worker crash != protocol state loss (recovery matrix);
- the arrow to the canonical repository ALWAYS terminates at Core for governed
  mutations (red controls 18, 19).

### 3.1 One root project family

One project has one runtime family (Core, scheduler, queue, scratch, SubSaipen
registry). Project identity uses the canonical project identity (resolved
project root), never raw path spelling: two aliases to the same project must
not create two Core writers (red control 29).

Required invariant: one project -> one active Core writer lease. A second Core
admission is REFUSE or ATTACH, never "start another writer" (red control 2).

Mechanisms ported for this: Prime's socket-lease single instance, generation
fencing, and session lease (`session-lease`, `daemon-supervisor-ownership`,
`daemon-socket`), reimplemented in Python stdlib.

## 4. Resident Core + `cc`

Today `cc` means "continue project context to convergence". v9 adds the
physical mechanism: `cc` authorizes/resumes convergence AND the resident
runtime can continue without the client remaining open. CC keeps obeying the
existing convergence order; the runtime does not redefine it.

```
user:  cc
SAIPEN: execution_intent = converge
runtime: keeps scheduling Core turns
Core:   reads STATE/BOARD, executes canonical next action
gate fails:  Core fixes it (existing behavior)
runtime budget expires: checkpoint, pause (PAUSED_BUDGET), not DONE
client exits: work continues if policy allows
actual SAIPEN closure: Core records DONE (evidence-based only)
```

A passed test gate proves only that gate. It never independently authorizes
SAIPEN DONE (red control 13).

## 5. Objective vs continuation policy

Prime Agent correctly separates a durable objective (goals) from policy
deciding whether another continuation happens (autonomous, deliberately not
persisted). Preserve that split.

SAIPEN already has `execution_intent` (normal | goal | converge). v9 adds a
runtime-owned `continuation_policy`. Do NOT merge them into one overloaded
flag (red controls 11, 12).

Example:

```
execution_intent: goal        objective remains active
continuation_policy: resident runtime may autonomously request the next Core turn
```

A token/time/turn limit stopping continuation is `PAUSED_BUDGET`, never
`DONE`. SAIPEN closure remains evidence-based.

Continuation policy fields (all safety valves):

```
max_continuations
max_turns
max_tokens
max_wall_time
gate_timeout
gate_retries
```

Limit reached -> checkpoint, persist runtime state, pause execution, remain
resumable. Never mark the task complete.

## 6. Queue

Adopt Prime's steering-vs-follow-up distinction. Runtime queue item classes:

| Class | Delivery |
|---|---|
| STEER | deliver at the next safe model boundary during active work |
| FOLLOW_UP | deliver after the current unit/turn finishes |
| NEXT | ordinary queued task after the current SAIPEN action |
| SCHEDULED | becomes eligible at its specified time |

No arbitrary text is injected mid-tool-mutation. Every delivery occurs at an
explicit safe boundary (model-call boundary, never inside a tool call).

Queue state is persisted durably. Crash/restart must not lose accepted
messages (red control 6).

### 6.1 Exactly-once semantics

Ported from Prime's command-recovery journal (received/result/acknowledged,
uncertain-never-replayed). Queue item:

```
id            project_id      created_at
type          payload         status
eligible_at   claimed_at      delivered_at
source
```

Lifecycle: `queued -> claimed -> delivered`, plus `cancelled` and `uncertain`.

A crash after claim but before known delivery enters `uncertain`; the runtime
must not blindly replay an uncertain destructive instruction (red controls 7,
8, 25). No duplicate sends because a process restarted.

## 7. Heartbeats and schedules

Port Prime's cron store concept (once | interval | cron; claim-then-dispatch;
missed-tick coalescing). Every tick produces only a PROMPT / WAKE EVENT; it
does not mutate canonical project state directly (red control 9).

Examples: wake Core after model limit reset; retry a BLOCKED external
condition; check whether long tests finished; run periodic SAIPET observation;
resume CC at a configured time.

Due schedule: claim first, then deliver, so crash recovery does not blindly
duplicate the tick. Missed repeated ticks coalesce — no accumulation of 700
identical "check tests" prompts after a machine slept overnight.

## 8. State classification (never silently merged)

CANONICAL (Core-owned, unchanged by runtime):
- STATE, BOARD, LOG, KNOWLEDGE;
- accepted protocol configuration;
- canonical role charters;
- canonical USERPERSON where enabled.

RUNTIME DURABLE (runtime-owned, atomic writes, recoverable):
- accepted queue, schedules;
- process registry, runtime session IDs, child handles;
- continuation budgets, pending delivery receipts.

RUNTIME SCRATCH (disposable, never canonical):
- SAIREPL variables, parsed data, caches, temporary indexes,
  exploratory calculations.

TRANSCRIPT (observable history, evidence source, not canonical project state):
- runtime event stream and any session transcript.

## 9. Recovery matrix

| Event | Expected recovery |
|---|---|
| client crash | worker continues |
| supervisor crash | restart -> discover/recover workers or durable runtime records |
| Core model session loss | recreate from canonical SAIPEN + runtime queue state |
| SubSaipen crash | mark runtime failed; preserve workspace/OUTBOX; Core decides retry/adopt |
| kernel (SAIREPL) loss | rebuild scratch; canonical work survives |
| machine reboot | durable queue/schedules/session metadata recover; no ambiguous destructive replay |
| corrupt runtime state | quarantine; canonical SAIPEN still boots without it |
| canonical SAIPEN corruption | normal Recovery applies; runtime may not invent replacement truth |

Port from Prime: worker-recovery journal (busy/operation), orphan-process
journal, command-recovery journal, generation fencing, PID+processStartId
liveness, stop-requested tombstones. All reimplemented, Windows-first.

## 10. Continuation / limit-reset automation

One explicit v9 target: SEND/RESUME WHEN MODEL LIMIT RESETS. Runtime provider
adapters may detect rate limit, usage limit, reset timestamp, retry-after,
provider unavailable. With reliable reset evidence: persist wake condition,
schedule resume, detach cleanly. Without a known reset time: bounded
retry/backoff. Never hammer providers. Never fake reset timestamps.

This is the use case that finally removes the repeated human
`continue / continue / continue` loop.

## 11. Retained SubSaipens

Prime retains useful child sessions. Adapt with SAIPEN's freshness rules.

SubSaipen remains the semantic worker contract (charter, OUTBOX, freshness
fields). v9 adds an OPTIONAL runtime handle. Runtime record:

```
sub_id  role  runtime_session  status  role_revision
source_fingerprint  last_message  retained
```

Status: `ephemeral | retained | stopped | stale`.

Retained means its runtime/context MAY be resumed. It does NOT mean previous
conclusions are fresh. Before reused work is accepted, role_revision, source
fingerprint, and OUTBOX freshness must still pass current SAIPEN rules (red
controls 15, 16). Runtime continuity never overrides semantic freshness.

HUNT helpers stay ephemeral: narrow investigation -> result -> terminate.
Retention has a cost; do not retain every agent because the runtime makes it
possible.

## 12. Direct agent messaging

Ported from Prime's family-only direct messages with receipts. Allowed:
Core -> SubSaipen; SubSaipen -> Core; Core -> sibling through controlled
routing; sibling -> sibling only where explicitly authorized.

Message record: `message_id sender receiver created_at delivery_mode
payload_hash status`. Delivery modes: `steer | follow_up`.

Messages are TRANSPORT, not TRUTH (red control 17). A message may say
"I found a race in scheduler.py" but nothing becomes canonical until Core
verifies -> ticket/LOG/OUTBOX evidence.

No peer message can mutate canonical STATE, append canonical LOG, move BOARD
tickets, or authorize a destructive action. A SubSaipen message "apply this
patch" does not authorize main-tree mutation: Core receives, checks freshness,
reviews, owns the mutation, verifies the result (red controls 17, 18).

## 13. SAIREPL — optional persistent Python control environment

Prime's persistent IPython is useful but SAIPEN correctness must never depend
on it. SAIREPL is an OPTIONAL runtime scratch environment: parsed data, helper
functions, temporary indexes, test results, runtime handles, computational
scratch, loaded Python skills. It may survive turns, compaction, and client
detach. It remains CACHE/SCRATCH.

Canonical truth stays in files. After complete runtime loss, a fresh agent +
repository files must reconstruct the project (red controls 5, 20, 21). If
losing the kernel makes the project unknowable, v9 failed.

Port from Prime (reimplemented, stdlib): state-snapshot via a portable
serializer with tolerant restore (missing/corrupt => empty, never throws),
atomic write via temp + replace, per-variable skip for unpicklable/oversize.

## 14. Prompt-as-data (without making chat history canonical)

Adopt the useful RLM concept: large context may be handled programmatically
rather than stuffed into every model turn. Examples: expose repository
snapshots as queryable variables; hold parsed BOARD indexes; query LOG slices;
retrieve specific evidence; summarize tool results before model injection.

But: the conversation transcript is NOT canonical project memory.
STATE/BOARD/LOG/KNOWLEDGE remain authoritative. Runtime context reduces token
pressure; it never replaces the protocol.

REJECTED from Prime: session JSONL as canonical trace. Prime uploads raw
session JSONL as the trace. SAIPEN's canonical record is STATE/BOARD/LOG/
KNOWLEDGE; the runtime event stream is diagnostic only.

## 15. Compaction

Compaction is runtime housekeeping, never DONE, never checkpoint proof, never
handoff proof. Before compaction, durable work must already be represented in
SAIPEN canonical state. After compaction, Core reloads or verifies STATE,
active BOARD, the relevant current phase, and active role/context.

Kernel/scratch state may survive compaction, but the agent must not rely
exclusively on the compaction summary. Prime's own design confirms this: the
summary is lossy text, the kernel snapshot is the lossless state, and the
model is told the summary "won't appear above". SAIPEN goes further: the
canonical files are the lossless state; SAIREPL is optional.

## 16. Skills

Ported distinction: instruction skill (markdown) vs executable skill (python
package). Potential SAIPEN executable skills:

```
saipen_validate()
saipen_freshness()
saipen_sub_spawn()
saipen_sub_status()
saipen_queue()
saipen_schedule()
saipen_hunt_probe()
```

APIs typed and boring. A skill is reusable capability; it must not secretly
define protocol law. Protocol semantics remain in canonical documents/tests.

## 17. Improve bridge — take the idea, not Prime's mutation model

Prime `/refine` can mutate prompts, memories, skills, subagent specs with
plan/review/apply/rollback and an immutable base prompt. SAIPEN already has
the stricter planned mechanism: `saipen improve`.

Do NOT replace Improve with `/refine`. Map the concept as:

```
trajectory / runtime evidence
    -> Improve report
    -> Core sweep
    -> verified ticket
    -> tested change
```

No automatic mutation merely because the model thinks it learned something.
Prime-style supplemental state may exist later, but only under: proposal,
preview, evidence, Core approval, transactional apply, rollback.

### 17.1 Preview-before-apply is mandatory

For every self-improvement/harness mutation: PLAN -> DIFF -> REVIEW -> APPLY
-> VERIFY. An inspectable before/after representation exists BEFORE mutation.
Store: source evidence, proposed change, target, before hash, after hash,
approval route, verification, rollback snapshot (red control 26). This is
stronger than upstream, deliberately.

### 17.2 Transactional runtime writes

Every runtime-owned persisted write (queue, schedule, child registry, scratch
snapshot metadata, supplemental harness, runtime configuration) is atomic:
compute final bytes -> sibling temp -> flush -> atomic replace -> recover old
state on failure. Crash at any write point leaves OLD VALID STATE or NEW VALID
STATE, never half of both (red control 27). Port Prime's temp+rename pattern.

## 18. Process supervisor — Windows-first, Python stdlib

Do NOT adopt Node/TypeScript because upstream uses it. Port architecture, not
ecosystem. A minimal Windows-first supervisor with:

- one instance (lock + generation fencing);
- stable local IPC (named pipe on Windows; stdlib socket fallback elsewhere);
- no visible console required;
- start/stop/status;
- worker discovery;
- worker crash detection;
- restart policy;
- stale PID/lock recovery;
- clean shutdown;
- orphan cleanup (Windows Job Objects via ctypes/Python stdlib with a
  capability probe);
- persistent queue/schedule ownership.

## 19. Windows is first-class

Prime targets macOS/Linux. SAIPEN is Windows-first. Do NOT inherit POSIX
assumptions (signals, flock, PTYs, Unix sockets, chmod, symlinks, process
groups, shell quoting, daemonization). Every borrowed mechanism gets a Windows
implementation, a capability probe, and a Windows red control before it is
considered ported. Linux support remains desirable with architecture parity.

## 20. Security boundary

Prime's persistent Python/kernel processes are NOT a security sandbox. Keep
that explicit. Runtime worker separation exists for lifecycle, crash
containment, and ownership — never for malicious-code containment (red control
18 is about write authority, not code isolation). For untrusted code or
workspaces, require a real external sandbox: Hyper-V, Windows Sandbox,
container/VM, restricted user environment, or other explicitly supported
external isolation.

## 21. Observability

One machine-readable runtime event stream:

```
runtime.started  runtime.attached  runtime.detached
queue.accepted   queue.claimed     queue.delivered
schedule.due     worker.started    worker.failed
sub.spawned      sub.message       sub.completed
continuation.started  continuation.paused_budget
recovery.performed
```

Runtime event log is DIAGNOSTIC. It does not replace canonical SAIPEN LOG (red
control 28). Use correlation IDs instead of duplicating every protocol event.

## 22. SAIPENVIEW integration comes later

Only after the runtime API is stable: running agent list, attach/detach, queue
controls, scheduled sends, limit-reset wakeups, heartbeat controls, SubSaipen
runtime status, process health, stop/restart. SAIPENVIEW remains a client.
Closing it must not own or destroy work. saiui designs this interface later
under Golden Default; the runtime never couples to GUI widgets.

## 23. Command surface (candidates, not frozen)

```
saipen runtime status
saipen runtime start
saipen runtime stop
saipen runtime attach

saipen queue
saipen queue add
saipen queue cancel

saipen schedule
saipen schedule add
saipen schedule cancel
```

SubSaipen commands extend existing `saipen sub`, not a parallel family. `cc`
remains `cc`; the user should not need to know whether CC is resident or
foreground for its semantic meaning. Enable explicitly via
`saipen runtime enable` (final command chosen during design). Runtime OFF is
the default: the file protocol works exactly as before (red control 30).

## 24. Rejected Prime assumptions

Reject or redesign:

- canonical dependence on chat/session JSONL (SAIPEN canonical = files);
- kernel as source of project truth;
- unattended harness mutation;
- OS-permission execution marketed as sandbox;
- macOS/Linux-only assumptions;
- Prime-specific provider/account infrastructure;
- product TUI architecture SAIPEN does not need;
- unnecessary npm/TypeScript dependency;
- upstream UI/theme code;
- automatic child freedom that bypasses Core;
- any feature whose maintenance cost exceeds its SAIPEN value.

Every imported line must earn its existence.

## 25. Implementation philosophy

COPY SMALL / ADAPT HARD / TEST HARDER over FORK EVERYTHING / DELETE HALF /
PRAY. When upstream code is tightly coupled to its TypeScript runtime,
provider stack, TUI, or session format, reimplement the mechanism cleanly in
SAIPEN rather than dragging the dependency graph. Use Prime Agent as reference
implementation, source of failure knowledge, and source of tested mechanisms —
not as architectural authority.

Fork concepts aggressively; fork maintenance burden conservatively. Do NOT
vendor the repo. Preferred: isolate the checkout; identify the smallest useful
subsystem; copy/adapt only bounded units; strip Prime-specific assumptions;
wrap behind SAIPEN-owned interfaces; port upstream tests that prove the
mechanism; add SAIPEN-specific invariants.

Upstream tests are as valuable as upstream code: for every copied subsystem,
port the upstream behavior test first (local adapted failing test -> local
implementation -> SAIPEN invariant test). Prime's implementation bugs and open
issues are research input; upstream HEAD is not flawless because it has stars.

## 26. Vertical slices

### V9-M1 RESIDENT CONTINUE (first milestone)

Acceptance:
1. launch resident Core worker;
2. submit one normal SAIPEN task;
3. detach client;
4. Core continues safely;
5. runtime checkpoints;
6. kill client completely;
7. reconnect from a fresh client;
8. see correct running/completed state;
9. crash/restart supervisor;
10. restore without duplicate work;
11. canonical STATE/BOARD/LOG remain valid.

No RLM, no peer messaging, no UI. Prove residence first.

### V9-M2 QUEUE + SCHEDULE

Persistent queue; steer; follow-up; exact-time delivery; recurring heartbeat;
exactly-once claim/delivery. Acceptance includes machine-reboot recovery.

### V9-M3 RETAINED SUBSAIPEN

Spawn, status, retained context handle, direct Core<->child message, restart
recovery, freshness recheck, Core-only integration. One retained child first;
parallel families only after it is correct.

### V9-M4 SAIREPL

Optional persistent Python computational workspace: persists across turns,
survives compaction where possible, restart failure recoverable, never
canonical, SAIPEN fully works with the feature disabled.

### V9-M5 CONTINUAL IMPROVEMENT BRIDGE

Connect runtime trajectory/evidence to `saipen improve`. No auto-mutation.
Runtime may propose IMPROVE CANDIDATE; Core/Improve owns acceptance.

## 27. Red controls (before implementation)

1. closing client does not stop worker;
2. worker cannot create a second Core writer;
3. supervisor restart does not duplicate a running task;
4. runtime loss does not destroy canonical recoverability;
5. kernel (SAIREPL) loss does not destroy canonical recoverability;
6. queue message survives restart;
7. delivered queue message is not delivered twice;
8. uncertain delivery does not auto-replay destructive work;
9. heartbeat missed ticks coalesce;
10. schedule survives restart;
11. token limit pauses rather than DONE;
12. wall-time limit pauses rather than DONE;
13. passing one quality gate does not bypass SAIPEN DONE;
14. retained child survives parent compaction/reconnect where supported;
15. retained child stale source is rejected;
16. retained child old role revision is rejected;
17. direct message cannot mutate canonical state;
18. SubSaipen cannot become main-tree writer;
19. UI/client has no execution ownership;
20. SAIREPL disabled -> SAIPEN still fully works;
21. SAIREPL wiped -> cold recovery succeeds;
22. copied upstream code has provenance;
23. Windows process lifecycle passes natively;
24. stale lock/PID recovers safely;
25. machine reboot recovery does not duplicate scheduled mutation;
26. Improve proposal cannot apply without preview/review;
27. failed harness write leaves old state intact;
28. runtime diagnostic log cannot substitute canonical LOG;
29. project path aliases cannot create duplicate Core runtime;
30. v8 behavior remains unchanged when v9 runtime is OFF.

## 28. Backward compatibility

v9 runtime is initially OPTIONAL. Default migration path: the SAIPEN file
protocol works exactly as before. Enable explicitly (`saipen runtime enable`).
If the runtime is unavailable, fall back to ordinary cold agent execution.
A daemon installation is NEVER mandatory merely to read or maintain a SAIPEN
repository. A repository must remain portable.

## 29. gated v9 backlog

The detailed implementation backlog lives here (below), NOT on the hot BOARD.
The single gate ticket is BOARD T-575. The gate condition:

```
v8 sequential/concurrency contract stable
AND current Improve wave clean
AND canonical tests green
AND HUNT/CLEAN clean baseline
```

Until the gate opens, allowed: research, source mapping, prototypes in
isolated kitchen, architecture documents, red controls. Forbidden: replacing
the current Core runtime, changing existing command semantics, introducing a
second canonical state, silently depending on Prime Agent.

### Backlog (ordered by slice)

M1: supervisor + project runtime skeleton + lease + resident Core worker +
attach/detach + worker recovery journal + orphan journal + command journal +
runtime event stream + `saipen runtime {start,stop,status,attach}` + enable
gate + red controls 1-5, 18, 19, 23, 24, 29, 30.

M2: queue store (atomic) + steer/follow_up/next/scheduled + exactly-once
claim/deliver + uncertain recovery + schedule store + heartbeat + coalescing +
limit-reset wake scheduling + red controls 6-10, 25.

M3: SubSaipen runtime handle + retained/ephemeral status + direct messaging +
freshness recheck + Core-only integration + red controls 14-17.

M4: SAIREPL + tolerant snapshot/restore + optional skills + red controls
20, 21.

M5: Improve bridge + preview/review/transactional apply + red controls
26, 27, 28.

Across all: provenance enforcement (red control 22), difference-ledger
maintenance, Windows capability probes.
