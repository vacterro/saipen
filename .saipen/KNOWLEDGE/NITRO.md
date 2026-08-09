# SAIPEN NITRO — foundational mechanical acceleration (gated backlog)

NITRO introduces SAIOPS, a zero-dependency Python mechanical execution layer
that performs deterministic protocol operations agents currently do by
hand-editing STATE.md / BOARD.md / LOG.md. Primary purpose: move MECHANICS out
of LLM reasoning. The contract is `saipen/OPS.md`.

Target principle:

```
PROSE DEFINES WHY.
LLM DECIDES WHAT.
PYTHON DEFINES HOW.
TESTS PROVE THE RESULT.
```

NITRO is deliberately the sequential precursor to v8 Concurrent Mode and v9
resident runtime: ProjectSnapshot, operation preconditions, canonical project
lock, plan/apply split, operation IDs, journal/recovery, stale-plan refusal,
and typed results will all be reusable there. It is NOT a database, NOT a
service, NOT a rewrite of the validator in one ticket, and NOT permission to
start v8/v9.

## Architecture

`saipen_engine/` — one importable zero-dependency package:

```
saipen_engine/
    __init__.py  errors.py  result.py  paths.py  codec.py
    state.py     board.py    log.py     lock.py   journal.py
    phases.py    fast_check.py  plan.py  operations.py
    snapshot.py  subs.py
```

plus one thin executable adapter `tools/saipen.py`. Existing tools may import
the engine; the engine imports no application-specific UI/runtime code. One
operation, one implementation, invoked by CLI, runtime, SAIPENVIEW, and v9.
`model.py` was deleted (superseded duplicate of snapshot.py); the phase DFA
lives once in `phases.py` (validator imports it); project identity lives once
in `paths.project_identity` (lock and snapshot consume it).

## Hard invariants

- canonical files remain sufficient for cold recovery (delete caches/engine,
  a fresh agent still knows what happened, what is active, what to do next);
- state/board parsing has ONE reusable mechanical implementation (no parser
  drift among validate.py, the engine, run_scenarios.py);
- no false claim of multi-file atomicity: the write-ahead journal + the
  LOG -> BOARD -> STATE order are the truth;
- real OS single-writer locking (msvcrt / fcntl), not "lock file exists";
- unrelated BOARD content stays byte-identical under a surgical ticket move;
- encoding/BOM/newline metadata preserved on write unless a migration owns it;
- no third-party dependencies (stdlib only), no SQLite, no service;
- every mutation is PLAN / APPLY separated, dry-runnable, and journalled.

## Integrity sweep (T-584, after M6)

An external audit (2026-08-09) reproduced 12 defect hypotheses against the
live engine and found the closed M2-M5 guarantees materially weaker than their
tickets claimed. The sweep's core principle: make deterministic mechanics
actually deterministic before building self-improvement/concurrency on top.

Reproduction corpus: `tools/nitro_integrity_repro.py` -- every R1..R12 defect
built as an isolated fixture; all 12 now flip to NOT REPRODUCED. The behavioral
red controls replacing the proxy tests are `run_nitro_integrity_probes()` in
`tools/run_scenarios.py`.

What the repaired engine guarantees (and the red controls prove):

- truthful GENERIC journal stages: targets carry `path` + `role` + `before_hash`
  + `after_hash` + `applied`. No positional LOG/BOARD/STATE pseudo-semantics; a
  MANIFEST is never reported as LOG_WRITTEN.
- conflict-safe Recovery: per-target live hash == before -> apply staged;
  == after -> already applied; anything else -> CONFLICT, evidence preserved,
  refuse to guess. Recovery is idempotent.
- mandatory pending-op preflight before EVERY mutation: exactly one pending op
  is recovered first; conflict/multiple -> refuse. `saipen recover` exposes
  pending ops; status/next report real `recovery_pending`.
- immutable OperationPlan consumed by APPLY: one op_id, exact planned bytes,
  never recomputed. COMMIT FAILURE ALWAYS WINS over semantic success.
  WRITER_BUSY / STALE_STATE / CONFLICT / RECOVERY_REQUIRED are structured
  Results, never tracebacks.
- owned-field STATE patches: every operation declares the keys it owns;
  checkpoint/ticket_add/goal preserve phase/task/next_action; unrelated fields
  (mode, requires, intent, counters, unknown future fields) survive.
- shared LOG event builder with mechanical parent (`E-N -> E-(N+1)`).
- fast proposed-state validation before PREPARED + real post-write byte/cross-file
  verification before VERIFIED (VERIFIED means a verifier ran).
- codec genuinely preserves encoding/BOM/newline; journal stores exact final
  bytes; recovery replays them (UTF-8 LF/CRLF/BOM/UTF-16LE red controls).
- Improve writers journaled with path ownership, one active cycle, per-seat
  derived status, full sweep-finding coverage, disposition-enum validation,
  propagated commit results; append_run migrated.
- single phase DFA owner (`saipen_engine.phases`); one ProjectSnapshot
  (`snapshot.py`, `model.py` deleted); one project identity
  (`paths.project_identity`); module import floor in the probe suite.

## Claim-to-proof matrix (T-578..T-583)

Every meaningful verify clause now has either an executable red control or an
explicit statement that it is architectural/manual evidence. CLOSED != TRUE
FOREVER; PASS != CLAIM PROVED; a test can encode the bug (the old TODO->done
"PASS" and the checkpoint last_event-only probe are the precedents).

| Ticket | Claim (verify) | Proof | Status |
|---|---|---|---|
| T-578 M1 | shared parsers; ProjectSnapshot; status/next read-only | nitro probes (parsers, snapshot stale, status/next) | PROVEN |
| T-578 M1 | characterization parity | validator + scenario + audit green | PROVEN |
| T-579 M2 | real OS single-writer lock; path-alias identity | nitro-m2 lock probes + `paths.project_identity` single owner | PROVEN |
| T-579 M2 | write-ahead journal; roll-forward recovery | nitro-m2 crash injection PREPARE/LOG/BOARD/STATE | PROVEN |
| T-579 M2 | committed retry ALREADY_APPLIED; no duplicate LOG | nitro-m2 probes | PROVEN |
| T-580 M3 | PLAN/APPLY separated; dry-run zero bytes | nitro-m3 + nitro-integrity (plan dry-run, op_id == journal op_id) | PROVEN |
| T-580 M3 | claim moves exactly one ticket; ALREADY_CLAIMED | nitro-m3 probes | PROVEN |
| T-580 M3 | VALID_TRANSITIONS rejects illegal; ticket-bearing requires T-ID | nitro-m3 + phases.py single owner | PROVEN |
| T-580 M3 | LOG/BOARD/STATE ordering | journal.py CORE policy + crash probes | PROVEN |
| T-581 M4 | canonical ticket-ID allocation (skips T-998/999) | nitro-m3 next_ticket_id probe | PROVEN |
| T-581 M4 | add/done/block/unblock | nitro-m3 + nitro-integrity lifecycle probes | PROVEN |
| T-582 M5 | goal/cc counters; valve reauthorization | nitro-m3 goal probes | PROVEN |
| T-582 M5 | stop/checkpoint; dry-run | nitro-m3 + nitro-integrity (stop dry-run zero bytes) | PROVEN |
| T-583 M6 | Improve writers on common machinery | improve probes + nitro-integrity (path/cycle/sweep/propagation) + MANIFEST crash probe | PROVEN |

Regressions recorded under T-584 (R1..R12) and proven by
`tools/nitro_integrity_repro.py` + `run_nitro_integrity_probes()`.

## Milestones (one red-test -> implementation -> gates -> release each)

M1: shared parser + ProjectSnapshot extraction; saipen status; saipen next.
M2: lock + journal + recovery; crash-injection harness
    (NITRO_CRASH_AFTER_PREPARE/LOG/BOARD/STATE).
M3: saipen claim, transition, checkpoint.
M4: ticket lifecycle (add/done/block/unblock/update) + canonical ticket-ID
    allocation (ignores synthetic T-998/T-999 fixtures).
M5: goal/cc counters, safety-valve reauthorization, stop/checkpoint.
M6: migrate Improve mechanics (register_cycle/register_seat/
    write_sweep_entry/append_run) onto the common transaction primitive --
    register_cycle currently creates the cycle dir before the MANIFEST replace,
    so a crash can expose a roster-less cycle; fix via the general primitive.
M7: USERPERSON writers on common path/atomic/result/dry-run.
M8: SubSaipen operations (reuse freshness.py/sub_clean.py).
M9: context compiler (saipen context cold/hot/audit) + token accounting.

The first vertical slice is claim/transition/checkpoint. After those are
mechanical, STOP adding commands and use them in real Improve work; choose the
next operation from evidence, not an API museum.

## First red controls (30)

claim moves exactly one ticket; claim cannot duplicate a ticket; illegal claim
writes zero bytes; stale snapshot writes zero bytes; concurrent claim yields
one winner; path alias cannot create a second writer; event ID allocated
exactly once; event timestamp real UTC; crash before LOG leaves canonical
state unchanged; crash after LOG rolls forward exactly once; crash after BOARD
rolls STATE forward; crash after STATE validates and commits; repeated
recovery idempotent; repeated committed op does not duplicate LOG;
STATE.task == BOARD.DOING after every successful op; last_event == LOG tail;
illegal phase transition writes zero bytes; ticket-bearing phase requires exact
T-ID; dry-run changes zero canonical bytes; unrelated BOARD lines byte-identical;
encoding/newline preserved; malformed BOARD/STATE/LOG refuse before mutation;
writer lock releases after process death; second live writer refuses; fast
validator catches every cross-file mutation SAIOPS can create; full validator
passes after a successful operation; full validator fails a deliberately
corrupted post-state; engine deletion leaves the repository cold-readable.

## Ticket chain on the active board (normal T-IDs)

One gate + the next 2-3 executable tickets only. Detailed later milestones
stay here.
