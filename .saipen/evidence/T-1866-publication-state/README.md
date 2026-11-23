# T-1866 / SRC-295 F-03 — an `own_patch` DONE states its publication truth

## The defect

`saipen ticket done <T> --closure-mode own_patch` answered FINISHED while saying
nothing about whether the delta it just closed had been published. The audited
case is exact: a ticket was closed as `own_patch`, and fifteen minutes later the
implementation files it named were still modified in the worktree. A DONE line
that is silent about publication therefore reads as "shipped".

Two neighbouring gates did not cover the gap:

- T-37 already refuses `own_patch` when BUILD declared `implementation_delta none`
  — that is the *no code* case.
- `closure._resolve_work` already refuses to INHERIT an unpublished DONE as
  publication authority — that is the *downstream* case.

Between them sat the unhandled case: a real delta, genuinely closed, not released.

## Why this is not a refusal

The obvious stricter gate — refuse to close `own_patch` until a release names the
ticket — was rejected deliberately. Publication is blocked here for reasons an
individual ticket does not own (today: a foreign staged batch in the shared
index, 206 paths). A refusal would fail closed on every ordinary closure and turn
each one into an operator obligation, which is the exact inversion this Work
exists to remove: obstacles must become permitted actions, not duties.

So the closure proceeds and the DONE line *states* the fact:

```
closure_mode: own_patch | publication_state: pending
```

with the LOG completion event carrying the route that flips it:

```
ticket finished via SAIOPS -- completion (from SHIP); publication_state pending;
release route: saipen cohort ship <C-###> (a released batch names this ticket,
flipping the state to published)
```

The downstream `resolve_implementation_source` refusal is untouched and remains
exactly as strict. A `pending` DONE is still not publication authority.

## Derived, never asserted

`closure.publication_state(root, ticket_id)` is the single oracle. It is
read-only, scans the same committed release evidence `_resolve_work` trusts, and
returns one of two values — `published` or `pending`. It cannot be satisfied by
prose: no caller parameter reaches it on the finish path, because the engine
derives the value itself in `_plan_finish_ticket`.

Two values, not three: a third would be a state no reader could act on. The two
are exactly the two decisions available to a reader — inherit it, or release it
first.

## Five coupled surfaces

Wiring this field honestly required five coordinated edits, and each missing link
produced a real, diagnosed failure rather than a silent no-op:

1. `saipen/REGISTRY.json` → `ticket_states.known_fields`. Without it, an
   unrecognized field makes the whole BOARD record fail to parse.
2. `tools/saipen_engine/board.py` → `PUBLICATION_STATES`, `CLOSURE_METADATA_FIELDS`
   (so reopen/reconcile strips it), and validation: the value must be in the
   vocabulary, and only `own_patch` may carry it.
3. `tools/saipen_engine/board_compaction.py` → `COMPACTION_DISPOSITION`. This is
   checked at *import* time; without an entry the module raises
   `ValueError: compaction disposition is missing BOARD fields:
   ['publication_state']`.
4. `extensions/schemas/board.schema.json` → the property plus its DONE-only
   placement rule. The cross-doc drift check in `tools/validate.py` fails with
   `cross-doc drift [schemas] -- board.schema.json does not describe
   ['publication_state']` otherwise.
5. `tools/saipen_engine/operations.py` → the derivation in `_plan_finish_ticket`,
   the completion detail, the `_set_closure_fields` parameter, and the
   self-clearing `elif mode != "own_patch"` branch (a row that migrates from
   `own_patch` into a cohort must not keep state describing a delta its new mode
   says it does not own).

## Evidence

- `subject.diff` — the six subject files, `a/` = hunks removed, `b/` = shipped
  bytes. `+140 / -0`; no pre-existing line of any file is touched.
- `prefix-red-control.log` — the same bytes with the T-1866 hunks removed. Runner
  `verdict: FAIL`, `ran: 6`, exit 1; direct unittest detail appended in the same
  file names the three failures (`..._says_published`, `..._says_pending`,
  `..._names_its_own_publish_route`), `FAILED (failures=3)` in 0.517s.
- `postfix-green-control.log` — the shipped bytes. `verdict: PASS`, `ran: 6`,
  exit 0, record `dcfbfb5f55f3717b-20261023T181956869919Z`.

### How the before-state was produced

A whole-file `git checkout` would have been dishonest: these six files also
carry earlier uncommitted Work (`board.py` shows 603 changed lines,
`operations.py` 2010). The before-state was therefore reconstructed surgically —
each T-1866 hunk removed from a copy by exact string match, with an assertion
that the match occurs exactly once, and JSON re-parsed after every edit. The
reconstruction was then proven to be the same state the red log came from: with
it applied the focused run exits 1; restored, it exits 0. `subject.diff` is
generated from that same pair of byte sets, so the log and the diff cannot drift
apart.

## Test inventory (6)

| Test | Claim |
| --- | --- |
| `test_an_unpublished_own_patch_closure_says_pending` | a real delta with no release evidence closes and says `pending` |
| `test_a_published_own_patch_closure_says_published` | a receipt naming the ticket flips it to `published` |
| `test_the_pending_state_names_its_own_publish_route` | `pending` is never a dead end — the LOG names `saipen cohort ship` |
| `test_pending_is_derived_from_evidence_not_from_the_request` | `resolve_implementation_source` still refuses a `pending` DONE |
| `test_the_no_delta_refusal_is_untouched` | control: the T-37 refusal still fires (`implementation_delta none`) |
| `test_an_inherited_closure_claims_no_patch_state` | control: `inherited_verified` writes no `publication_state` |
