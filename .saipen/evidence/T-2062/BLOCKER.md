# T-2062 blocker -- measured, and why this session cannot lift it

Date: 2026-11-17. Head: `dc39709c0c17a3272126c01a626ffcaa4176140b`.

## Ready work (not applied)

The GC serialization package `PY-19` is verified against this exact tree:

- `kitchen/PY-19.patch` sha256
  `afb610b95dae93ba7e3eb88fdea241d428dd5c39a9225b65f2f587737c35cc7a`
- targets `tools/saipen_engine/gc.py` `f1921568…` and
  `tools/saipen_engine/lock.py` `30965c05…` (matches the current worktree)
- patched `gc.py` result `9fab03b3…`; 8/8 concurrency rounds clean, 63-case
  GC suite green (`E-21407`)
- the files are intentionally unmodified: the patch was never applied here.

## Why it is BLOCKED now

`E-21441` moved T-2062 to `## BLOCKED` with blocker text
`ACTIVE_DEPENDENCY:T-2059 -- ... T-2061 (WAIT_USER_DECISION, ...)`.

`saipen ticket unblock T-2062` refuses (`E-21442`):

```
WAIT_USER_DECISION: T-2062 is blocked on ACTIVE_DEPENDENCY:T-2059 -- ...
unblocking requires verified operator authority or authentic proof
```

The gate at `tools/saipen_engine/operations.py:6753` scans the whole blocker
prose for `WAIT_USER`, so the parenthetical description of T-2061 trips an
operator-owned gate even though the blocker CLASS is
`ACTIVE_DEPENDENCY`. Measured provenance of the unblock payload:

```
carrier_present: False
witness: {'witness': 'model_supplied', ... 'nothing compared them with what the operator wrote'}
```

No truthful proof token exists: no operator carrier, no live receipt, and the
T-2059/T-2061 condition has not changed.

## Other canonical routes, all measured closed

- `saipen undo` / `cut`: `CONFLICT -- foreign/unattributed changes overlap
  restore scope` (the shared dirty tree; reverting would cross unrelated work).
- `saipen recover --dry-run`: `CLEAN` (no board repair).
- `saipen ticket block` on a BLOCKED ticket: `ILLEGAL_TICKET_LIFECYCLE`.
- `saipen ticket done` on a BLOCKED ticket: illegal; DONE requires SHIP.
- `saipen ticket supersede`: needs `--authority SRC-###`, which this session
  cannot mint.
- Hand-editing `BOARD.md` is forbidden; BOARD changes only via `saipen`.

## Smallest operator action

One authenticated ZAICODE native ingress (the same `operator_carrier` T-2061
needs), then:

```
saipen ticket unblock T-2062 "<decision>"
saipen claim T-2062 --explicit
git apply .saipen/extensions/subs/saipython/kitchen/PY-19.patch
```

The claim does not itself enforce `needs: T-2059`; the decision text should say
whether implementation may precede publication (the patch stays unpublished,
no commit/push/install). Then SCOUT/BUILD/VERIFY with the anchored regression
pair, and close `own_patch` with the unpublished-publication state recorded.

No commit, no push, no install, no hand edit was made by this session.
