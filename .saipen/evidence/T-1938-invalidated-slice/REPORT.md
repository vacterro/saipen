# T-1938 — a disproven finding was recorded as implemented work

Status: closed `own_patch`, publication `pending` (see "What this does NOT prove").

## Where this came from

Not from the backlog: from the REVIEW self-audit of **T-1937**, and after that
ticket was already closed. T-1937 added `reconcile_slice_closures`, which derives
a promoted gate slice's closure from BOARD truth. Its mapping was:

```python
resolved = "superseded" if ticket in superseded else "done"
```

Every DONE ticket that was not `superseded_verified` became `done`. That is right
for `own_patch`, `cohort`, `inherited_verified` and `external_implementation` —
all of those really were implemented. It is wrong for **`finding_invalidated`**.

## Why `done` is a lie for that mode

The mode's contract is written in `operations.py` (T-406):

- it requires `--invalidated-by E-###`, an event in the ticket's own LOG chain;
- it writes `implementation_delta: none` — BUILD produced no code;
- it writes `invalidation_evidence` — which recorded event established that the
  ticket owed no delta.

So `finding_invalidated` means *the finding was disproven; nothing was owed and
nothing was built*. Recording that slice as `done` tells every later reader the
work exists. Future.md §1 already defines the right word for a slice that will
not be implemented: **`rejected`**.

Measured scope before the fix: BOARD carried five such tickets — T-1625, T-1639,
T-1699, T-1824, T-1869 — and **none is bound to a gate slice**, so the wrong
answer was latent, not live. That is why T-1937 could ship without it and why
this is a separate ticket rather than a reopened one.

## The repair

```python
if mode == "superseded_verified":
    superseded.add(...)
elif mode == "finding_invalidated":
    rejected.add(...)
...
if ticket in superseded:
    resolved = "superseded"
elif ticket in rejected:
    resolved = "rejected"
else:
    resolved = "done"
```

The mode set is now traversed only for tickets actually in `## DONE`; the loop no
longer collects a mode from a ticket that is still in TODO/DOING/BLOCKED, which
also removed a way for a stale `closure_mode` field on a live ticket to leak into
the derivation.

## Tests

`tools/test_t1938_invalidated_slice_closure.py` — 4 tests, green.

| Test | Pins |
| --- | --- |
| `test_an_invalidated_finding_closes_as_rejected` | the fix, and the reported change record |
| `test_an_implemented_ticket_still_closes_as_done` | `own_patch` and `inherited_verified` still `done` |
| `test_a_superseded_ticket_is_still_superseded` | precedence unchanged |
| `test_every_resolved_vocabulary_is_one_the_gate_accepts` | each resolved value empties `open_slices` and flips `closed` |

The third test is the one that matters for honesty: it is not enough that
`rejected` is written, it must be a value `open_slices` treats as resolved,
otherwise the slice reads closed in the index but the gate still refuses to
close. It is also asserted that the value is in `future_gate.CLOSURES`.

The fixture writes a **real gate document** and never relies on the
"document vanished" path. That mistake was made in T-1937's fixture and measured
there: with no document on disk, `build_index` copies the whole prior gate dict,
so every slice mutation is invisible and the test passes regardless of the code.

## Executed red controls

| # | Mutation | Target test | Result |
| --- | --- | --- | --- |
| C1 | the pre-fix mapping: `finding_invalidated` falls through to `done` | `test_an_invalidated_finding_closes_as_rejected` | FAILS (`'done' != 'rejected'`) |
| C2 | over-reach: every DONE ticket becomes `rejected` | `test_an_implemented_ticket_still_closes_as_done` | FAILS (`'rejected' != 'done'`) |
| C3 | precedence swapped: reject before supersede | `test_a_superseded_ticket_is_still_superseded` | FAILS (`'rejected' != 'superseded'`) |

All three fail with the *right* wrong value, so they discriminate the mapping
rather than just the presence of the function.

## Executed regression pair

Contract `.saipen/evidence/T-1938-invalidated-slice/execution-contract.json`
(`unittest`, `{python} -B tools/test_t1938_invalidated_slice_closure.py`).

Pre-fix carrier `.saipen/evidence/T-1938-invalidated-slice/pre/future_gate.py` =
current file with the mode branch reverted to T-1937's form; the function itself
is present, so the pair measures the MAPPING and nothing else.

Record `.saipen/evidence/regression/regression-execution-30667199548243d29a979dcf5df5901b.json`:

- before: exit 1, ran 4, **failed 1** — `AssertionError: 'done' != 'rejected'`
- after: exit 0, ran 4, failed 0 — `OK`

This is a stronger pair than T-1937's. There the pre-fix half was 8 red of 9
because the function did not exist, which proves presence, not wrongness. Here
the subject exists and behaves, and exactly one assertion catches it producing
the wrong value while three controls keep it from over-correcting.

## What this does NOT prove

- **`obsolete` remains unreachable.** FUTURE.md §1 lists four resolutions;
  BOARD truth can derive `done`, `superseded` and now `rejected`, but nothing
  says when a slice is `obsolete`. That gap predates both tickets and is not
  claimed closed here.
- **No live slice was closed by this change.** The five `finding_invalidated`
  tickets are not bound to any gate slice, so the fix was proven on fixtures and
  a preserved pre-fix carrier, not on a live gate.
- **Publication is `pending`.** Same operator staging condition as T-1937: a
  commit cannot be isolated without either staging the release scope explicitly
  or leaving the operator's in-flight batch untouched.
