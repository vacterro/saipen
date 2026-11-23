# T-1937 — FUTURE gate slice closure had no writer

Status: closed `own_patch`, publication `pending` (see "What this does NOT prove").

## The defect, measured

`future_gate.record_slice()` has exactly one caller: `saipen.py:7811`, inside the
`future promote` handler, and it passes no `closure`, so every promoted slice is
written `"open"`. Nothing else advanced a slice, and `future refresh` only
re-hashed documents. The consequence is structural, not cosmetic:

- `readiness()` answers `INELIGIBLE, ("N slice(s) still open on a promoted gate",)`
  (`future_gate.py`, readiness branch) for a promoted gate with any open slice;
- `PROMOTED` is in `TERMINAL_STATES`, so the gate can never re-enter the candidate
  class either.

A gate whose entire promoted Work was finished therefore stayed INELIGIBLE for
ever. Measured on the live project before the fix: **T-1936 was `[x]` under
`## DONE` on BOARD while `.saipen/future/index.json` still read
`closure: "open"` for FG-0046's slice.**

`saipen/FUTURE.md` §1 already specifies the intended end state — a gate closes
when every slice is DONE/SUPERSEDED/REJECTED/OBSOLETE — so the specification had
no implementation, not an ambiguous one.

## The repair

`future_gate.reconcile_slice_closures(root, board_tickets=None)` derives the
closure from BOARD truth:

- a ticket `[x]` under `## DONE` closes its slice as `done`;
- a ticket whose `closure_mode` is `superseded_verified` closes as `superseded`;
- a ticket still in `## TODO`/`## DOING`/`## BLOCKED` leaves the slice `open`;
- a ticket merely **absent** from BOARD closes nothing — absence could as easily
  be a truncated parse, and a closure writer that guesses is the same class of
  defect as a hand-edited index;
- an already-resolved slice is never rewritten.

The signature deliberately exposes **no closure, state or verdict parameter**.
`test_the_verb_takes_no_caller_supplied_closure` pins that: the whole point is
that the answer is derived, so an argument would reintroduce the hole.

Two entry points consume it:

1. `future refresh` now reconciles after rebuilding, so a routine refresh carries
   BOARD's DONE truth into the projection;
2. `saipen future reconcile` is the explicit canonical verb (added to `_future()`'s
   accepted actions in `tools/saipen.py`), and `future refresh --json` now reports
   `slice_closures`.

### Live measurement

`saipen future reconcile --json` on the real project, first run:

```json
{"ok": true, "code": "FUTURE_SLICES_RECONCILED",
 "changes": [{"gate": "FG-0046", "ticket": "T-1936", "closure": "done"}],
 "mutation": "index"}
```

Second run: `"changes": [], "mutation": "none"` — idempotent, and the closure it
wrote is still present in the index.

## A real regression this change introduced, and how it was found

Wiring the derivation into `refresh()` made it read `.saipen/BOARD.md`
unconditionally. `refresh` is the projection builder and is legitimately called
on corpus-only fixtures, so an absent BOARD became `FileNotFoundError`. **This was
found by a neighbour suite, not by T-1937's own suite**:
`test_t1618_future_maturation.Auto14PerformanceTests` P1 and P2 both construct a
`project/` tree with `future_gate/` documents and no BOARD, and both errored.

Fixed by treating an absent BOARD as "no ticket is proven DONE" — the
conservative answer that closes nothing — while a *malformed* BOARD still returns
`BOARD_MALFORMED` rather than silently closing everything. Pinned by
`test_a_tree_without_board_still_refreshes`, with red control C4 proving it bites.

The lesson is recorded because it is the general one: a derivation wired into a
shared builder inherits that builder's call sites, and those call sites are not in
the new ticket's test file.

## Tests

`tools/test_t1937_future_slice_closure.py` — 9 tests, green.

| Test | Pins |
| --- | --- |
| `test_a_done_ticket_closes_its_slice` | DONE → `done`, one change reported |
| `test_a_superseded_ticket_closes_as_superseded` | superseded → `superseded` |
| `test_a_todo_ticket_stays_open` | TODO unchanged, `mutation: none` |
| `test_a_ticket_absent_from_board_does_not_close_anything` | absence is not DONE |
| `test_an_already_closed_slice_is_not_rewritten` | idempotence |
| `test_the_verb_takes_no_caller_supplied_closure` | no `closure`/`state`/`resolved` parameter |
| `test_a_tree_without_board_still_refreshes` | the absent-BOARD regression |
| `test_a_rebuild_does_not_reopen_a_derived_closure` | `refresh` preserves a derived closure |
| `test_readiness_stops_reporting_open_slices` | the consequence: `open_slices` empties, `closed` flips |

Fixtures write the index through `future_gate.write_index()` rather than raw JSON.
An earlier version hand-wrote the dict and silently omitted the index `marker`,
which produced four confusing errors; a fixture that builds its own JSON stops
testing the real index contract the moment that contract grows a field.

### The fixture that lied, found by REVIEW

The first fixture declared a gate (`FG-9001`) with **no gate document on disk**.
`build_index` has a deliberate path for exactly that: a document that vanished
keeps its whole prior record (`gates.append({**raw, ...})`), so the closure came
back through a blind copy instead of the entry builder. Measured consequence: a
mutation that emptied `"slices"` in the entry builder left the test green,
meaning the test was asserting something other than what its name claimed.

With the fixture now writing a real `FG-9001_fixture.md` the control bites:

| Control | Mutation | Result |
| --- | --- | --- |
| C5 | carry-forward from the prior index dropped | FAILS as required |
| C5b | re-derivation in `refresh` dropped, carry-forward intact | STILL GREEN — correct, not a gap |
| C5c | both dropped | FAILS as required |

C5b green is the honest measurement of how the two mechanisms relate: the
re-derivation re-reads BOARD, but it can only rewrite slice records that the
carry-forward preserved. Dropping either one alone is insufficient to lose the
closure; dropping the carry-forward alone is sufficient.

## REVIEW self-audit

Two defects, both in this ticket's own delta, both fixed here rather than
deferred:

1. **`future refresh` reported `slice_closures` from a run that could never see
   anything.** The branch called `refresh()` (which reconciles) and then called
   `reconcile_slice_closures()` again to produce the report. The second call
   always found nothing left to do, so the field would have read `[]` for ever
   even when a closure had just been written. Fixed by deriving *before* the
   rebuild and reporting that result.
2. **The absent-BOARD regression** (above), found by a neighbour suite.

Also confirmed during the audit: `closed` requires `state == PROMOTED` and a
non-empty `slices`, so a slice cannot be "closed" on a gate that was never
promoted; and the validator's rules 4/5/6 (`future_gate.py:1621`–`1660`) gain no
new failure from a resolved slice.

## Tests


## Executed red controls

All mutations to `tools/saipen_engine/future_gate.py`, source restored after each,
each run against one named test.

| # | Mutation | Target test | Result |
| --- | --- | --- | --- |
| C1 | absence from BOARD treated as DONE | `test_a_ticket_absent_from_board_does_not_close_anything` | FAILS as required |
| C2 | every slice closed regardless of section, always `done` | `test_a_todo_ticket_stays_open` | FAILS as required |
| C3 | already-closed slices rewritten (idempotence removed) | `test_an_already_closed_slice_is_not_rewritten` | FAILS as required |
| C4 | absent BOARD raises instead of proving nothing | `test_a_tree_without_board_still_refreshes` | FAILS as required |

## Executed regression pair

`--regression required` on BOARD, so an admitted, measured pair is owed rather
than prose. Contract:
`.saipen/evidence/T-1937-future-slice-closure/execution-contract.json`
(`unittest`, `{python} -B tools/test_t1937_future_slice_closure.py`, timeout 300).

Pre-fix subject carrier:
`.saipen/evidence/T-1937-future-slice-closure/pre/future_gate.py` — the current
file with **exactly** the T-1937 hunk removed (`reconcile_slice_closures` deleted,
`refresh` restored) and nothing else, so the pair attributes the delta to this
change rather than to the operator's other uncommitted edits in the same file.

Final measured record
`.saipen/evidence/regression/regression-execution-17c5bdfaa90a4309a4fed0531284f844.json`:

- before: exit 1, ran 9, **failed 8**
- after: exit 0, ran 9, failed 0 — `OK`

Honest reading of that number: the pre-fix half is 8 red of 9 because the function
is absent, so it proves the repair exists rather than that each behavioural claim
was previously violated. The *behavioural* discrimination comes from the five
mutation controls above, which fail for the right reasons. The 9th test
(`test_a_tree_without_board_still_refreshes`) is green pre-fix by construction: it
guards a regression this ticket introduced, not the original defect.

Two earlier pairs are superseded, each by a real subject change rather than by
prose: `regression-execution-a815c2c4843243aa989cb668158d88c4` (7 tests, before the
absent-BOARD fix) and `regression-execution-93a27a591ae04fb8b5538e3c1cb8fceb`
(8 tests, before the fixture repair and the double-reconcile fix).

### A verifier-digest trap worth naming

The record's `verifier` digest folds in a digest of the **process environment**.
`saipen work regression` and `saipen transition VERIFY -> REVIEW` therefore must
run in the same shell invocation: measured here as `STALE_REGRESSION_EVIDENCE:
verifier or subject bytes changed` on an unchanged tree, because the two commands
were issued from separate Bash calls with different ambient environment. Running
them in one invocation cleared it with `ALREADY_APPLIED`. This is behaviour of the
existing gate, not something T-1937 changed, but it silently invalidates a
correctly measured pair and is easy to misread as a real staleness.


## Neighbour coverage

The focused family run covers `test_t1614_future_gate.py`,
`test_t1618_future_maturation.py`, `test_t1638_future_ingress.py`,
`test_t1641_gate_ownership.py`, `test_t1882_future_publication_inventory.py` and
the new suite. `test_t1618_future_maturation` is the suite that caught the
regression, so its inclusion is load-bearing and not a formality.

## What this does NOT prove

- **No gate was observed completing its full lifecycle.** The live run closed one
  slice (FG-0046/T-1936) and the index now reports 1 PROMOTED gate with no open
  slices; that gate still does not *become* ELIGIBLE, because `PROMOTED` is
  terminal by design. The claim here is narrower than "gates now close": it is
  that a slice can finally reach a resolved closure, which was previously
  impossible.
- **`REJECTED` and `OBSOLETE` are not derived by this writer.** Only `done` and
  `superseded` are reachable from BOARD truth. A gate needing the other two still
  has no canonical route; that is a separate gap, not a claim made here.
- **A `finding_invalidated` ticket would be recorded as `done`.** Found by the
  REVIEW self-audit after T-1937 was already closed, so it could not be fixed
  under this ticket's authority (source is frozen post-DONE). The writer maps
  `superseded_verified` to `superseded` and everything else to `done`, but
  `finding_invalidated` means the premise was DISPROVEN and no work was
  implemented — `done` is the wrong answer. Measured: BOARD carries five such
  tickets (T-1625, T-1639, T-1699, T-1824, T-1869) and none is bound to a gate
  slice, so it is latent rather than live. Tracked as **T-1938** with
  `--regression required`.
- **`saipen.py`'s dispatch hunk is not covered by the executed pair.** The
  contract's subject is `future_gate.py` only, because that is the file whose
  bytes actually differ from the pre-fix carrier; the CLI branch is additive
  routing and is exercised by the live `saipen future reconcile` measurement
  above, not by the measured pair.
- **Publication is `pending`.** The operator has ~294 foreign paths staged; a
  commit touching this work cannot be isolated without either staging the release
  scope explicitly or leaving that batch untouched. Per ship.md step 6b.3 the
  bytes were left alone.
