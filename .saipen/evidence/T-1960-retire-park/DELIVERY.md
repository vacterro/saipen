# T-1960 — `ticket retire` could not retire a blocked ticket

## The defect

`retirement.RETIRABLE_SECTIONS` names `## BLOCKED`, so a blocked row is a legal
retirement subject. But a blocked row can also be the sole evidence for the one
deliberate non-DFA STATE pair:

```
transition_from: SCOUT -> phase: DONE
```

`fast_check.block_parked_evidence_error()` accepts that pair only as the
canonical active-ticket park, and its proof is *the blocked ticket still sitting
in BOARD.BLOCKED*. `_retire_targets` removes that row inside the same
transaction and then validates its own proposal — so the operation destroyed the
evidence its proposal depended on and failed against it:

```
proposed retirement state fails fast validation: STATE proposed invalid
phase transition: SCOUT -> DONE (RFC § 1.6). The block-parked shape requires
the latest phase-changing event through STATE.last_event to be the canonical
active-block DEC for the exact ticket still in BOARD.BLOCKED
```

`unblock` is not an alternative door. `operations` refuses it outright when
`retirement.non_work_event()` finds the canonical classification:

```
TICKET_NOT_WORKABLE: T-1958 is INVALID_INVOCATION;
removing a blocker does not reclassify non-Work
```

Each door refuses on the other's precondition. There was no canonical route to
remove a misrouted blocked row.

## The fix

`ticket_move` and `finish_ticket` already normalize this exact pair to the
actual `DONE -> DONE` self-transition when a structural move follows a park.
`ticket retire` is the third writer of a neutral STATE and was the one that
never did. It now does the same, scoped identically: only when `phase` is
`DONE` and `transition_from` is one of the five ticket-bearing phases, i.e.
exactly the pair no longer justified by the row being removed.

`tools/saipen_engine/operations.py`, `_retire_targets`:

```python
elif state.get("phase") == "DONE" and state.get("transition_from") in (
    "SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP",
):
    owned["transition_from"] = "DONE"
```

No validator was weakened, no gate was bypassed, no ledger row was hand-edited.
The park still cannot be claimed without its blocked row.

## Evidence

| item | measurement |
|---|---|
| new oracle | `tools.test_ticket_retirement.BlockParkedRetirementTests`, 3 tests |
| red control | fix neutralized → `test_retiring_the_blocked_ticket_succeeds_and_clears_the_park` FAILs with the exact production message above |
| green | fix restored → 3/3 OK |
| regression | full `tools.test_ticket_retirement` = 58 tests OK (1 pre-existing skip) |
| scoping control | `test_a_neutral_state_is_left_alone` — a non-park retirement leaves `phase: BUILD` / `task: T-7` untouched |
| shape control | `test_the_park_shape_is_the_one_that_blocked_the_operation` asserts `phases.transition_legal("SCOUT", "DONE") is False`, so the test is aimed at the real non-edge |
| lint | `ruff check tools/test_ticket_retirement.py` clean; `operations.py` keeps only its 2 pre-existing findings (RUF059 at 12520, E501 at 12563), confirmed identical against `git show HEAD:` |
| live | `ticket retire T-1958` succeeded in production after the fix (E-19244) after refusing with this message before it |
