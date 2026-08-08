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
    __init__.py  errors.py  result.py  paths.py  codec.py  model.py
    state.py     board.py    log.py     lock.py   journal.py
    transaction.py  operations.py  context.py
```

plus one thin executable adapter `tools/saipen.py`. Existing tools may import
the engine; the engine imports no application-specific UI/runtime code. One
operation, one implementation, invoked by CLI, runtime, SAIPENVIEW, and v9.

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
