# FUTURE GATE — deferred authority candidates

<!-- RULE-OWNER: FUTURE-GATE-01 -->

A FUTURE GATE is a **deferred authority candidate**: a recorded idea, design,
roadmap or defect hypothesis whose operator is NOT authorizing implementation
yet. It is not Work, not a rule source, and not implementation authority.

The distinction that makes the class safe:

- A gate that is already implemented, blocked or owned by live Work is not a
  deferred candidate. It is a **trash bin for hard bugs** and is forbidden.
- A gate that restates intent the operator already gave is a Source. Record it
  as a Source; do not bury it in the deferred class.
- A gate that is really a plan for the current ticket is ordinary TODO.

## 1. Lifecycle

```
RECORDED ──> DEFERRED ──┬──> INELIGIBLE  (terminal; not a candidate)
                        └──> ELIGIBLE ──> PROMOTED ──> ordinary Work
                                                             │
                                    DONE / BLOCKED / SUPERSEDED / PARTIAL
```

`PROMOTED` ends the gate lifecycle. A promoted gate is no longer routing truth
— the Work it created owns that truth from then on. The gate record survives as
provenance and closure accounting only.

- `RECORDED`: captured, not yet evaluated for readiness.
- `DEFERRED`: evaluated and not yet eligible; the live candidate class.
- `INELIGIBLE`: mechanically disqualified at intake (see §3). Terminal.
- `ELIGIBLE`: readiness proven; the sole routable candidate class.
- `PROMOTED`: bound to canonical Work.
- `NEEDS_REVIEW`: the historical record is ambiguous. Truthfully unknown, never
  `ELIGIBLE` by guess.

**Partial promotion is supported.** One promotion binds ONE bounded slice and
records it. The gate stays open with the residual deferred, and closes only when
every slice is `DONE`, `SUPERSEDED`, `REJECTED` or `OBSOLETE`. A gate with one
unresolved slice is not closed and is not `ELIGIBLE` again.

## 2. Storage

- `future_gate/**.md` — the human-readable gate document. Design, context and
  rationale live here. It carries the machine header
  (`<!-- SAIPEN FUTURE GATE v1 -->` plus the fields of §4).
- `.saipen/future/index.json` — the machine-owned projection. Lifecycle facts,
  identity, readiness inputs, the corpus witness and slice closure only.
- `.saipen/future/records/FG-####.json` — the reviewed-record side-car (§9). It
  is the machine authority for a document that never carried a machine header.

Routing reads the index. It MUST NOT reparse arbitrary long Markdown on every
`continue`. A document with no machine header is `NEEDS_REVIEW`, not `ELIGIBLE`.

**Identity is `FG-####` and MUST NOT depend solely on filename.** The index
assigns the id and reconciles it by (declared id) → (document digest) →
(normalized title), so renaming or moving a document keeps its identity.

### 2.1 Freshness

The index is **derived state**, so its truth is measured against the corpus it
claims to describe. Every projection carries a witness: schema version,
canonical document paths with their digests, the document count, and a
fingerprint over them. Freshness classifies the pair:

| state | meaning |
| --- | --- |
| `CURRENT` | the witness matches the corpus exactly |
| `STALE` | the corpus changed, or the witness is absent or schema-drifted |
| `MISSING` | there is no index at all |
| `CORRUPT` | the index exists and cannot be parsed |

**A stale projection is not an empty one.** `MISSING`, `STALE` and `CORRUPT`
MUST NOT authorize the HUNT/ADD fallthrough. Such a projection reports no
eligible gate *and* names the mechanical repair it needs, so routing refreshes
before — never instead of — inventing fresh work. A `CORRUPT` index is rebuilt
from the corpus; it is never read as "there is no future work".

The one exception is `MISSING` over an **empty** corpus: with no document on
disk there is nothing to discover and nothing to refresh, so every rung below the
Future layer is reached exactly as it was before this rule existed.

### 2.2 Automatic discovery

The refresh is **mechanical and the protocol runs it itself**. When the Future
layer is reached with a non-`CURRENT` projection, continuation classifies the
route as `FUTURE_GATE_REFRESH`, executes `saipen future refresh` and reroutes.
The operator never types an import command for a document that already exists:
adding, editing, renaming or deleting a file under `future_gate/` is enough, and
the repair is announced with its `before`/`after` state.

A read-only session performs none of it. It restates the stale condition, names
`saipen future refresh` as the canonical next action, and writes nothing.

## 3. Intake

A gate is recorded when any of these is present:

- the operator says so explicitly ("record a future gate", "defer this",
  "not yet — park it", "consider this later");
- a document lands in `future_gate/`;
- a self-declaring handoff says it defers;
- a canonical operation records one (`saipen future add`).

Weak or inferred classification is allowed. **FUTURE GATE is not a
procrastination sink**: a hard bug, a ticket-shaped unit of work or something the
operator asked for enters TODO/Source/BLOCKED, never here. An inferred gate that
turns out to be urgent Work is promoted, not buried.

## 4. Readiness (`ELIGIBLE`)

Every condition must hold, all of them mechanically checkable:

1. state is `DEFERRED` or `ELIGIBLE`, and no slice is unresolved on a
   `PROMOTED` record;
2. `slice:` names ONE bounded unit that can finish inside one ticket;
3. `evidence:` references at least one existing path in the repository;
4. every `needs:` prerequisite is `## DONE` on BOARD (`needs: none` declares
   that there are none);
5. no ticket bound by a slice record is still open (a mention binds none);
6. `basis:` is not `speculative` when a measurable alternative exists;
7. the document is machine-readable (or carries a reviewed record bound to
   these exact bytes, §9) and carries no secret-like value.

A gate that fails a condition is **not eligible**, and the index records the
named reason. A failed readiness check is NOT a lifecycle transition: the gate
keeps its `DEFERRED` state, because one unmet prerequisite must not retire a
sound candidate forever. `INELIGIBLE` and `NEEDS_REVIEW` are intake
classifications (§3), never side effects of a check.

## 5. Idle priority

MAINTENANCE's autonomous halt falls through in this order, and only in this
order:

operator input → DOING/recovery → workable TODO → actionable unconsumed audit
→ refresh a non-CURRENT projection → **eligible FUTURE GATE** → ONE bounded
refinement of an ambiguous record → HUNT → ADD

FINISH outranks everything. A gate MUST NOT preempt active Work, MUST NOT
outrank an actionable audit layer, and MUST NOT preempt a live operator gate
(`STATE.improve_gate`, CORE § 1.11 UNBLOCK). The refresh and the refinement sit
*inside* the Future layer: neither is a rung the operator must climb, and
neither outranks a rung above it. With no `ELIGIBLE` gate and nothing ambiguous
left, routing reproduces today's HUNT → ADD behavior unchanged.

A stale, missing or corrupt projection stops the ladder **above** HUNT and ADD
(§2.1), so the fallthrough can never invent fresh work over an unexamined
corpus. A `MISSING` projection over an empty corpus does not (§2.1, last
paragraph).

Distinguish two halts:

- **BOARD HALT** — no workable TODO and no DOING.
- **AUTONOMOUS WORK EXHAUSTED** — BOARD HALT **and** no actionable audit
  **and** no eligible gate.

Only AUTONOMOUS WORK EXHAUSTED falls through to HUNT/ADD. Idle can never
deadlock: every branch of the ladder ends in executable work or an honest stop.

## 6. Selection

Deterministic, one gate at a time. Ordered:

1. explicit operator activation (`saipen future promote FG-####`);
2. explicit `priority:` (`P0` before `P1` …);
3. prerequisite-unblocked gate tied to the most recently completed Work;
4. `basis: measured|reproduced` before `basis: speculative`;
5. smaller bounded slice (`estimate:` in slices);
6. oldest `recorded_at:`.

Ties break on ascending `FG-####`.

**Never activate more than one gate at a time**; a second promotion waits for
the first Work to reach DONE.

## 7. Promotion

Promotion is a canonical mutation through the existing Source/Work authority —
never a side channel, never a hand-written ticket line.

1. re-evaluate readiness against current bytes;
2. bind provenance: the FG id, the document digest and the slice;
3. take ONE bounded slice;
4. link the Work back to its `FG-####`;
5. record durably (LOG event, index slice closure);
6. leave the residual deferred;
7. enter ordinary SCOUT → … → SHIP.

Blocked Work does not get a second ticket for the same root cause: its gate may
sit `READY_BUT_DUPLICATE` / unpromoted until the blocker resolves.

### Modes

- **Read-only** — list and evaluate only; never mutate the index, never promote.
- **Goal mode** — a promotion MUST NOT bypass the safety valve. Evaluating
  readiness consumes no ticket count; promoting consumes exactly one, under the
  existing caps, and a closed valve defers the gate rather than exceeding it.

## 8. Historical corpus

Indexing and classification are the first half of migration; **refinement** is
the second. Indexing is **non-destructive**: no historical document is rewritten,
moved or deleted. Ambiguous records classify as `NEEDS_REVIEW`, never `ELIGIBLE`
by guess. A missing or unreadable index is a truthful "unindexed" state — it
never fabricates readiness.

## 9. Refinement and reviewed records

A corpus of historical documents is not a corpus of executable work. Guessing
that every one of them is executable is the failure mode §3 forbids, so an
ambiguous record is **normalized**, never assumed.

**Refinement reads ONE document, classifies it from its own recorded status,
and records the verdict.** It is bounded by construction: one document, one
closed-vocabulary verdict, one write. It never rewrites the original, never
grants implementation authority, and never produces a ticket.

The verdict is one of:

| verdict | when |
| --- | --- |
| `RESOLVED` (`INELIGIBLE`) | the text claims implementation by `T-###` **and** that ticket is `## DONE` on BOARD — a closed cause, recorded as closed |
| `DEFERRED` | the text declares itself not implemented, deferred, follow-up, unauthorized, or partially implemented — the residual intent is preserved as-is |
| `ARCHITECTURE_SEED` (`DEFERRED`) | the text is a broad architecture record; it stays gated until one bounded slice is named |
| `ELIGIBLE` candidate (`DEFERRED`) | the text names live unfinished work and the operator or agent binds `--slice` and `--evidence` |
| `NEEDS_REVIEW` | the text states none of the above — truthfully unknown |

**A claim of implementation is verified, never trusted.** `IMPLEMENTED by T-1`
is `RESOLVED` only when T-1 is `## DONE` on canonical BOARD; otherwise the record
stays `NEEDS_REVIEW` and says which ticket to verify. Resolution is a verdict
about the past and never creates Work for an already closed cause.

**The reviewed record is the side-car `.saipen/future/records/FG-####.json`.**
It binds the verdict to the document path, its digest, the declared status, the
title and any facts the prose never stated (`slice`, `evidence`, `needs`,
`priority`, `basis`, `estimate`). A record whose digest no longer matches the
bytes on disk is **stale**: the gate returns to `NEEDS_REVIEW` and says
`reviewed record is stale for current bytes; refine again`. A review can never
be inherited by an edit.

**Refinement is bounded per run and never deadlocks continuation.** It runs
when, and only when, no `ELIGIBLE` gate exists and an ambiguous record is
unreviewed. Continuation classifies the route as `FUTURE_GATE_REFINEMENT`,
refines ONE record, records the verdict and **reroutes in the same chain** — a
verdict is not a stopping point. A reviewed record is offered exactly once, so
a corpus cannot spin on one document, and the per-chain budget bounds the pass
regardless. The next document is refined by the next run.

Refinement grants no authority: a refined gate is still deferred Work-candidate
authority, and promotion stays with §7's ordinary Source/Work ingress.