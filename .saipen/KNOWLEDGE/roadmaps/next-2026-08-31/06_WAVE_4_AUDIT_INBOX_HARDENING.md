# 06 — WAVE 4: NATIVE AUDIT INBOX HARDENING

## Goal

Keep the existing implementation, fix uncovered edge cases, and raise it from good v1 to reliable shared infrastructure.

## H1 — Lowest WORKABLE layer, not first ACTIVE layer

Current projection returns the first ACTIVE audit layer.

The router checks that one Work for workability.

If it is blocked, routing falls to ordinary BOARD and never examines a later audit.

Fix the interface.

Preferred architecture:

Audit Inbox returns ordered structural candidates.

Router remains authority for BOARD workability.

Conceptually:

```text
projection:
  cleanup candidates
  active candidates ordered by layer
  new candidates ordered by layer
  invalid diagnostics

router:
  active candidate 1 unworkable → try candidate 2
  ...
  first workable audit wins
```

Do not move BOARD parsing/workability policy into `audit_inbox.py`.

## Required regressions

1. layer 1 ACTIVE / linked Work blocked; layer 2 ACTIVE / Work workable → layer 2 wins.
2. layer 1 ACTIVE blocked; layer 2 NEW → layer 2 ingest wins before ordinary BOARD.
3. all audit candidates unworkable; ordinary BOARD workable → BOARD wins.
4. no BOARD and all audit candidates blocked/invalid → truthful audit diagnostic, never Improve idle.

## H2 — Fix invalid diagnostic duplication

Current projection builds the invalid list with a duplicated nested loop.

Multiple invalid layers should appear once each.

Add exact regression.

## H3 — Status/action consistency

Ensure:

- status projection;
- next projection;
- continue router;
- explicit `saipen audit status`;
- explicit `saipen audit ingest`;

all describe the same candidate ordering.

One ordering authority.

## H4 — Automatic cleanup ordering

Closed unchanged generations remain cleanup-first at the Audit Inbox stage.

But active project Work still outranks Audit Inbox globally.

Preserve this.

## H5 — Binding integrity

Add malformed binding tests:

- duplicate layer key impossible after JSON decode;
- missing receipt;
- bad generation;
- bad digest;
- stale work ID;
- changed file after closed binding.

Fail safely.

## H6 — Crash matrix completeness

Existing tests are good.

Add explicit restart tests using real journal recovery for:

- PREPARED before unlink;
- unlink done / binding update not done;
- binding update done / LOG commit torn;
- changed bytes before replay.

## Completion bar

1. 57 existing tests remain green;
2. new blocked-lower-layer tests green;
3. no invalid diagnostic duplication;
4. status/next/continue agree;
5. crash matrix green;
6. no second BOARD/workability implementation exists.
