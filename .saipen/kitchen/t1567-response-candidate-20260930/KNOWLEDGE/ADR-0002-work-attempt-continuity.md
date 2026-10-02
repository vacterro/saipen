# ADR-0002: Work/Attempt separation and cold-handoff continuity (T-1148)

## Status

Accepted (v7.226.x hardening wave). Implemented in the engine, the release
validator and the canonical continuity suite.

## Context

SAIPEN's durable unit was always the BOARD ticket (the Work): identity,
description, dependency edges and evidence live on BOARD/LOG and survive any
agent. But nothing distinguished *the work* from *one agent's bounded try at
it*. When a session died mid-ticket -- context window exhausted, provider
limit, crash -- the successor found only a stale claim and prose in LOG.
Three questions had no machine answer:

1. Why did the previous execution stop? (`context_limit` vs crash vs
   deliberate handoff changes what the successor does next.)
2. Is this a NEW try at the SAME work, or unrelated work?
3. Which claims did the previous producer make, and were they ever
   independently verified before the ticket closed?

Kungfu-style solutions (append-only mmap journals, SQLite authority, episode
ontologies, runtimes wrapping each provider) all violate SAIPEN's
file-first, stdlib-only, no-daemon constitution.

## Decision

**Borrow the semantics, reject the machinery.**

1. **Attempt = machine-owned DEC events in the existing append-only LOG**
   (`attempt A-### open|close`, closed result/stop vocabularies plus a
   result->stop matrix) **plus one optional STATE pointer** (`attempt: A-###`)
   written and cleared by two new engine operations inside the existing OPS
   transaction layer (LOG target + STATE target, crash-safe by the same
   ordering every mutation already uses). No fourth authoritative file, no
   daemon, no database, no per-attempt directory tree.

2. **Work identity is untouchable by attempts.** An Attempt close never
   moves a BOARD line, edits a description, or fails a ticket. A failed,
   interrupted or yielded episode leaves the Work exactly as claimable as
   before; the successor closes the dangling episode honestly
   (`interrupted` / stop `unknown` when the predecessor could not speak)
   and re-claims.

3. **Completion authority stays where it was -- and gets teeth.** The
   producer's own success can never admit its output: an open producing
   attempt blocks `ticket done`; a DONE ticket whose latest attempt closed
   `candidate` FAILs validation unless a VERIFY boundary exists AFTER that
   close ([attempt-admission]). Claim -> Evidence -> Verdict -> Transition
   was already enforced by closure-evidence and the SHIP gate; attempts pin
   the ORDER between a producer's claim and the independent verification
   that admits it.

4. **Cold handoff is a projection, never authority.** `saipen brief`
   synthesizes Work/objective/current-or-last attempt/stop reason/blockers/
   unknowns/next action from STATE+BOARD+LOG and prints it (human or stable
   JSON). It writes nothing, executes nothing, and deleting its output loses
   no information.

5. **Known vs unknown is recorded, not invented.** An Attempt close may carry
   ONE bounded `unknown:` clause; brief surfaces those under KNOWN
   UNCERTAINTY. Uncertainty never substitutes for verification evidence
   (H11 proves it fail-closed).

6. **Compatibility.** Everything is additive and optional. Legacy projects
   with no attempt events are readable as-is ("attempt history not
   recorded"); no synthetic historical attempts are ever generated. The
   strict `additionalProperties: false` STATE schema means an OLD install
   reading a NEW state refuses fail-closed on the unknown `attempt` field --
   the sanctioned direction for unsupported future state.

## Consequences

- Successor agents recover WHY work stopped, not just WHAT remains
  (previous_attempt + stop_reason in every brief).
- Attempt lineage (supersedes chains) is validated acyclic, unique and
  ticket-coherent across sealed + active history.
- SC-CONTINUITY-001 (tools/continuity_probes.py) exercises the full path
  deterministically with mock agent identities: claim -> die -> cold resume
  -> same-Work completion -> independent verification.
- Hostile matrix H1..H20 pins the failure modes: duplicate IDs, lineage
  cycles, self-admission, stale-evidence reuse, torn pointers, replayed
  lifecycle ops (idempotent), unknown-as-fact, legacy truth preservation.

## Non-goals

No attempt runtime, no provider adapters, no distributed consensus, no
second writer. Single-writer Core semantics unchanged: one open attempt
project-wide, enforced at open time and validated everywhere else.
