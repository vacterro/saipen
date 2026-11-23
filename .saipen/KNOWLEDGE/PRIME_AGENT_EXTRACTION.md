# Prime Agent Extraction Audit — v9 research

Pinned upstream: Prime Agent
  repo:   https://github.com/PrimeIntellect-ai/prime-agent
  commit: a18809e00ea30638584d87b3afea7285a9d7296c (2026-08-07)
  license: MIT (Copyright 2025 Mario Zechner)
  checkout: isolated research/reference location (not vendored).

This file records every candidate mechanism studied, its source location, its
classification for SAIPEN v9, the tests worth porting, and acknowledged
failure modes. Nothing here is copied code; this is the KEEP/MODIFY/REJECT
decision record. When a mechanism is later implemented, the actual code units
moved are recorded in `saipen/runtime/UPSTREAM.json` with mode
copied/modified/reimplemented/inspired.

Source map of studied areas (commit a18809e):

```
packages/coding-agent/src/modes/daemon/        supervisor, worker protocols, journals, heartbeats
packages/coding-agent/src/modes/session-worker/ owned headless worker
packages/coding-agent/src/modes/rpc/            JSONL RPC surface
packages/coding-agent/src/modes/headless-completion.ts, print-mode.ts
packages/coding-agent/src/core/agent-session.ts        session runtime + host handlers
packages/coding-agent/src/core/agent-session-runtime.ts session lifecycle
packages/coding-agent/src/core/agent-session-lease.ts  filesystem lease
packages/coding-agent/src/core/session-manager.ts      JSONL session persistence
packages/coding-agent/src/core/rlm-runtime.ts          RLM host bridge
packages/coding-agent/src/core/rlm-max-depth.ts
packages/coding-agent/src/core/autonomous.ts           continuation policy
packages/coding-agent/src/core/goals.ts                durable objective
packages/coding-agent/src/core/cron-jobs.ts            schedules + heartbeat cron
packages/coding-agent/src/core/compaction/             lossy context compression
packages/coding-agent/src/core/kernel/                 IPython kernel, fork server, snapshot, boot-gate
packages/coding-agent/src/core/refinement/             /refine plan/apply/rollback
packages/coding-agent/src/core/skills.ts, skill-blocks.ts
packages/coding-agent/src/core/agent-messages.ts       direct messaging
packages/coding-agent/src/core/agent-traces.ts         JSONL trace upload (rejected for SAIPEN)
packages/coding-agent/src/core/session-action-store.ts
packages/coding-agent/src/core/prompt-admission.ts
packages/coding-agent/src/core/usage.ts                token accounting
packages/agent/src/agent.ts, agent-loop.ts, types.ts   generic loop + queues
prime-agent-runtime/src/rlm/__init__.py, harness.py, skill.py
```

## Per-mechanism classification

Template: SOURCE / PURPOSE / PRIME OWNERSHIP / SAIPEN EQUIVALENT /
KEEP-MODIFY-REJECT / LICENSE IMPACT / TESTS TO PORT / FAILURE MODES.

### M-01 Daemon supervisor / worker separation

- SOURCE: `modes/daemon/daemon-supervisor.ts`, `daemon-mode.ts`,
  `daemon-supervisor-ownership.ts`, `daemon-socket.ts`,
  `daemon-worker-protocol.ts`, `daemon-client.ts`.
- PURPOSE: one supervisor process owns socket/descriptors/journals; one worker
  per root session runs the live agent; clients attach/detach freely.
- PRIME OWNERSHIP: supervisor owns catalog/supervision; worker owns the live
  session.
- SAIPEN EQUIVALENT: SAIRUNTIME supervisor owns runtime records; Core session
  owns the canonical execution loop.
- CLASSIFICATION: KEEP (concept) / MODIFY (reimplement in Python stdlib,
  Windows-first; supervisor never owns protocol truth).
- LICENSE IMPACT: reimplemented, not copied — no Prime code reused. If a
  bounded unit is later copied, preserve MIT notice in THIRD_PARTY_NOTICES.md.
- TESTS TO PORT: daemon-supervisor-process.test.ts (attach/adopt/recovery),
  daemon-supervisor-monitor.test.ts, daemon-supervisor-admission.test.ts,
  daemon-supervisor-heartbeats.test.ts, daemon-supervisor-eviction.test.ts,
  suite/regressions/4600-supervisor-singleton.test.ts,
  4603-worker-recovery.test.ts.
- FAILURE MODES: crash-between-writes, split-brain (generation fencing),
  PID reuse, stop-vs-crash race, eviction races. These are the exact hazards
  SAIPEN v9 red controls 1-5, 23, 24, 29 target.

### M-02 Single-instance lease + generation fencing

- SOURCE: `daemon-socket.ts` (lockfile + stale 5s), `session-lease.ts`
  (pid+startId lease, symlink aliases), `daemon-supervisor-ownership.ts`
  (generation owner dir, candidate + atomic rename).
- PURPOSE: exactly one live owner; stale/PID-reuse recovery; path-alias
  identity.
- SAIPEN EQUIVALENT: one project -> one active Core writer lease (section 3.1).
- CLASSIFICATION: KEEP (concept) / MODIFY (Windows named pipe or lockfile;
  canonical project identity not raw path spelling).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: session-lease.test.ts (second-owner reject, dead-owner
  reclaim, pid-reuse reclaim, symlink alias), daemon-socket.test.ts,
  4600-supervisor-singleton.test.ts.
- FAILURE MODES: pid reuse, stale lock, alias to same project creating two
  writers.

### M-03 Command-recovery journal (exactly-once, uncertain-no-replay)

- SOURCE: `modes/daemon/command-recovery-journal.ts`.
- PURPOSE: received->result->acknowledged with fsync; crash after receipt but
  before result => uncertain, never replayed; truncated tail tolerated.
- SAIPEN EQUIVALENT: queue claim/deliver exactly-once (section 6.1).
- CLASSIFICATION: KEEP (concept + bounded mechanics) / MODIFY (SAIPEN queue
  item schema, project_id scoping).
- LICENSE IMPACT: reimplemented (small, generic journal pattern).
- TESTS TO PORT: command-recovery-journal.test.ts (uncertain-not-replay,
  truncated tail, ack removal).
- FAILURE MODES: replay of destructive instruction after crash; that is
  red controls 7, 8, 25.

### M-04 Worker-recovery journal

- SOURCE: `modes/daemon/worker-recovery-journal.ts`, daemon-mode.ts
  RECOVERY_CHECKPOINT_EVENTS.
- PURPOSE: per-session busy/operation record; crash => mark interrupted, never
  auto-resume a mid-mutation operation.
- SAIPEN EQUIVALENT: worker recovery state (red control 3).
- CLASSIFICATION: KEEP (concept).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: worker-recovery-journal.test.ts;
  4603-worker-recovery.test.ts (generation-only replacement).
- FAILURE MODES: resurrecting work that may have partially completed.

### M-05 Orphan-process journal

- SOURCE: `core/orphan-process-journal.ts`.
- PURPOSE: pid + ownerPid + processStartId; reap orphans only when the owning
  process is confirmed dead; pid-reuse guard.
- SAIPEN EQUIVALENT: orphan cleanup (Windows Job Objects with capability
  probe).
- CLASSIFICATION: KEEP (concept) / MODIFY (Windows-native process groups).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: orphan-process-journal.test.ts.
- FAILURE MODES: killing a reused pid, orphan leak.

### M-06 Heartbeat catalog + cron store

- SOURCE: `modes/daemon/heartbeat-catalog.ts`, `core/cron-jobs.ts`.
- PURPOSE: recurring/one-shot schedules; claim-then-dispatch; missed-tick
  coalescing; uncertain dispatches never replayed; heartbeat = recurring cron.
- SAIPEN EQUIVALENT: runtime heartbeats + schedules producing only
  PROMPT/WAKE (section 7).
- CLASSIFICATION: KEEP (concept) / MODIFY (SAIPEN: PROMPT/WAKE only; no
  direct canonical mutation).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: cron-jobs.test.ts (parse, one-shot, claim/dispatch/recovery,
  heartbeat deferral, steer-vs-follow_up, coalescing);
  daemon-supervisor-heartbeats.test.ts.
- FAILURE MODES: duplicate tick after reboot, 700 accumulated "check tests"
  prompts after sleep.

### M-07 Autonomous continuation policy

- SOURCE: `core/autonomous.ts`.
- PURPOSE: in-memory continuation policy (deliberately not persisted); limits
  maxContinuations 3 / maxTurns 12 / maxTokens 80k / timeout 30min; gates run
  post-turn; cache-read tokens excluded from budget; stop = injected user
  message, never DONE.
- SAIPEN EQUIVALENT: continuation_policy separate from execution_intent
  (section 5).
- CLASSIFICATION: KEEP (concept) / MODIFY (SAIPEN bounds configurable;
  PAUSED_BUDGET state).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: suite/agent-session-autonomous.test.ts (injection, gates,
  retry-exhaust, token accounting).
- FAILURE MODES: budget reached mistaken for completion — SAIPEN red controls
  11, 12, 13.

### M-08 Durable goals (objective)

- SOURCE: `core/goals.ts`.
- PURPOSE: thread_goal_state persisted; statuses idle/active/paused/
  budget_limited/complete/error; objective XML-tagged, untrusted.
- SAIPEN EQUIVALENT: execution_intent (goal/converge) already exists; v9 does
  not add a second goal store.
- CLASSIFICATION: REJECT as a new mechanism (SAIPEN already owns intent);
  the persisted-goal discipline is already matched by STATE.
- TESTS: suite/agent-session-goal.test.ts (informational only).
- FAILURE MODES: n/a for SAIPEN (no new mechanism).

### M-09 RLM prompt-as-variable

- SOURCE: `rlm-runtime.ts`, `prime-agent-runtime/src/rlm/__init__.py`.
- PURPOSE: prompt is a string argument; tools are programmatic calls; depth-
  capped recursion.
- SAIPEN EQUIVALENT: prompt-as-data (section 14).
- CLASSIFICATION: MODIFY (SAIPEN context handling only; never canonical).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: interactive-mode-rlm-max-depth-command.test.ts (depth cap
  only).
- FAILURE MODES: unbounded recursion depth (SAIPEN: bound by policy).

### M-10 Persistent IPython kernel + snapshot

- SOURCE: `core/kernel/`, `tools/ipython.ts`, `state-snapshot.ts`.
- PURPOSE: persistent kernel as the model's primary tool; dill snapshot
  (disposable scratch, tolerant restore, per-variable skip); survives turns
  and compaction.
- SAIPEN EQUIVALENT: SAIREPL optional scratch (section 13).
- CLASSIFICATION: MODIFY (SAIPEN: optional, noncanonical, never required).
- LICENSE IMPACT: reimplemented (stdlib; no dill/ipykernel dependency until
  SAIREPL slice).
- TESTS TO PORT: kernel-state-roundtrip.test.ts, kernel-state-snapshot.test.ts
  (tolerant restore, corrupt snapshot, byte cap).
- FAILURE MODES: kernel loss must not destroy canonical recoverability —
  red controls 5, 20, 21.

### M-11 Compaction

- SOURCE: `core/compaction/`.
- PURPOSE: lossy context compression; kernel snapshot is the lossless state;
  summary truth != full truth.
- SAIPEN EQUIVALENT: compaction as housekeeping only (section 15).
- CLASSIFICATION: KEEP (concept) / MODIFY (SAIPEN canonical files are the
  lossless state; compaction never touches them).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: compaction.test.ts, suite/agent-session-compaction.test.ts
  (informational for the prompt-summary shape).
- FAILURE MODES: summary mistaken for checkpoint/handoff proof — SAIPEN red
  control 4.

### M-12 Session JSONL persistence

- SOURCE: `session-manager.ts`, `agent-session.ts` (JSONL + artifacts dir).
- PURPOSE: transcript as durable session state; migrations.
- SAIPEN EQUIVALENT: transcript is TRANSCRIPT (section 8), never canonical.
- CLASSIFICATION: REJECT as canonical (SAIPEN canonical = files). The
  artifact-dir pattern (session-artifacts/<id>/) may inform SAIREPL scratch
  layout.
- LICENSE IMPACT: n/a (rejected).
- TESTS: informational only.
- FAILURE MODES: chat JSONL becoming project truth — the exact hole the goal
  names.

### M-13 Direct agent messaging

- SOURCE: `core/agent-messages.ts`.
- PURPOSE: family-only direct messages; receipts delivered|queued; steer vs
  follow_up; prompt format canonical text.
- SAIPEN EQUIVALENT: runtime messaging transport (section 12).
- CLASSIFICATION: KEEP (concept) / MODIFY (SAIPEN: transport, never truth;
  Core-only integration).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: kernel-agent-message-skill.test.ts (reach enforcement).
- FAILURE MODES: message mutating canonical state — red controls 17, 18.

### M-14 Skills (instruction vs executable)

- SOURCE: `core/skills.ts`, `skill-blocks.ts`,
  `prime-agent-runtime/src/rlm/skill.py`.
- PURPOSE: markdown instruction skill vs python importable executable skill.
- SAIPEN EQUIVALENT: SAIPEN skills (section 16) — typed, boring, never law.
- CLASSIFICATION: KEEP (concept) / MODIFY (SAIPEN skill set;
  protocol-neutral).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: skills.test.ts (discovery/validation/import metadata).
- FAILURE MODES: skill secretly defining protocol law (forbidden).

### M-15 Continual harness / /refine

- SOURCE: `core/refinement/refinement.ts`, `prime-agent-runtime/src/rlm/harness.py`.
- PURPOSE: mutate prompts/memories/skills/subagent specs; base system prompt
  immutable; plan->review->apply->rollback; before/after recorded;
  baseline-version conflict rejected; auto-refine gated.
- SAIPEN EQUIVALENT: `saipen improve` + preview/review/transactional apply
  (section 17).
- CLASSIFICATION: MODIFY (SAIPEN: Core/Improve owns acceptance; no automatic
  mutation; preview-before-apply mandatory).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: refinement.test.ts (base-prompt immutability, plan/apply/
  rollback, concurrent-edit conflict, rollback history).
- FAILURE MODES: unattended mutation — red controls 26, 27.

### M-16 RPC JSONL surface

- SOURCE: `modes/rpc/`.
- PURPOSE: strict LF JSONL on stdin/stdout; methods prompt/steer/follow_up/
  queue/schedules/heartbeats/observe; events buffered until ack.
- SAIPEN EQUIVALENT: runtime IPC style (stdlib-parseable).
- CLASSIFICATION: KEEP (concept) / MODIFY (SAIPEN command surface).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: rpc-prompt-response-semantics.test.ts (queued-prompt ack).
- FAILURE MODES: interleaved output (take-over-stdout discipline).

### M-17 Trace upload / telemetry

- SOURCE: `core/agent-traces.ts`.
- PURPOSE: upload raw session JSONL with trace headers.
- SAIPEN EQUIVALENT: none (local runtime event stream only, section 21).
- CLASSIFICATION: REJECT (remote telemetry; SAIPEN observability stays local
  and diagnostic).
- LICENSE IMPACT: n/a.
- TESTS: n/a.
- FAILURE MODES: n/a.

### M-18 Fork-server warm template

- SOURCE: `core/kernel/fork-server.ts`.
- PURPOSE: fork a warm kernel to skip ~1.2s import; Linux-only.
- SAIPEN EQUIVALENT: optional SAIREPL startup optimization.
- CLASSIFICATION: REJECT for v9 (Windows has no fork; revisit only with a
  capability probe, e.g. Windows Subsystem for Linux or process reuse).
- LICENSE IMPACT: n/a.
- TESTS: kernel-fork-server.test.ts (informational).
- FAILURE MODES: Linux-only assumption — the goal rejects inherited POSIX
  assumptions.

### M-19 Bash executor / sandbox

- SOURCE: `core/bash-executor.ts`; upstream sandbox via @anthropic-ai/
  sandbox-runtime.
- SAIPEN EQUIVALENT: external sandbox boundary (section 20).
- CLASSIFICATION: REJECT as runtime-owned security (SAIPEN runtime separation
  is lifecycle/ownership, never malicious-code containment).
- LICENSE IMPACT: n/a.
- TESTS: n/a.
- FAILURE MODES: marketing OS-permission execution as sandbox — explicitly
  forbidden by the goal.

### M-20 Agent loop queues (steer/follow-up/continuation)

- SOURCE: `packages/agent/src/agent.ts`, `agent-loop.ts`.
- PURPOSE: steering polled at start + after each turn; follow-up polled only
  when the agent would stop; continuation last; messages injected only at
  turn boundaries.
- SAIPEN EQUIVALENT: queue delivery at safe boundaries (section 6).
- CLASSIFICATION: KEEP (concept).
- LICENSE IMPACT: reimplemented.
- TESTS TO PORT: agent-loop.test.ts (inject after tool calls, continuation
  before stop, follow-up precedence), agent.test.ts (steer/follow-up queues).
- FAILURE MODES: injecting text mid-tool-mutation (forbidden).

---

## Difference ledger (Prime behavior -> SAIPEN behavior -> reason)

| Prime | SAIPEN | Reason |
|---|---|---|
| child results arrive through runtime messaging | runtime messaging transports results; canonical acceptance still requires OUTBOX/Core verification | single-writer law (red control 18) |
| persistent kernel contains useful runtime state | kernel/SAIREPL state is disposable scratch; repository must remain sufficient for cold recovery | hard SAIPEN invariant (red control 21) |
| session JSONL is the durable trace and can be uploaded | transcript is TRANSCRIPT; STATE/BOARD/LOG/KNOWLEDGE are canonical; runtime event stream is diagnostic local-only | chat history must never become project truth |
| /refine can auto-mutate supplemental state (gated) | Improve owns acceptance; preview/review/transactional apply mandatory; no automatic mutation | evidence-based closure |
| autonomous limits default 3/12/80k/30min, in-memory | continuation_policy is runtime-durable and configurable; PAUSED_BUDGET is a state, never DONE | bounded autonomous continuation |
| supervisor/worker/daemon in TypeScript with Unix sockets + POSIX signals | Windows-first Python stdlib; named pipe/lockfile; capability probes + Windows red controls | SAIPEN target is Windows-first |
| goals persisted inside session JSONL | execution_intent already canonical in STATE; v9 adds no goal store | no second canonical state |
| child subagents freely spawned with runtime context | retained SubSaipen runtime handles still gated by role_revision/source/OUTBOX freshness | runtime continuity never overrides semantic freshness |
| kernel fork-server (Linux only) | rejected; no POSIX-only mechanism enters v9 | Windows-first |
| traces uploaded with provider auth | observability is a local machine-readable runtime event stream | no remote telemetry, no provider dependency |

---

## License / provenance strategy

- Prime Agent is MIT. Nothing is copied in this research wave.
- When implementation begins, every copied/adapted unit is recorded in
  `saipen/runtime/UPSTREAM.json` (mode copied/modified/reimplemented/inspired,
  upstream_repo, upstream_commit, upstream_path, local_path, license) and the
  MIT copyright notice is preserved in `THIRD_PARTY_NOTICES.md`.
- Code that is merely conceptually similar and independently implemented is
  NOT attributed to Prime. Conversely, copied code is never claimed as
  independently authored.
- Do not vendor the upstream repo. Isolate the checkout; copy bounded units;
  strip Prime-specific assumptions; wrap behind SAIPEN interfaces; port tests
  first.

## Prime bugs / open issues as research input

Upstream HEAD is not treated as flawless. The acknowledged failure modes above
(crash-between-writes, PID reuse, split-brain fencing, uncertain-no-replay,
snapshot tolerance, compaction-truth hazards) are treated as the failure
knowledge the SAIPEN design must encode, and each maps to a red control.
