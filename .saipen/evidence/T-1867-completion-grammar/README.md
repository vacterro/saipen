# T-1867 — the canonical completion event stayed parseable when it grew

## The defect

T-1866 made the `own_patch` completion event carry its publication decision in
the **same** LOG event:

```
ticket finished via SAIOPS -- completion (from SHIP); publication_state pending; release route: saipen cohort ship <C-###> (a released batch names this ticket, flipping the state to published)
```

A fixed string became a small grammar. `supersession._COMPLETION_RE` still
matched that event with `fullmatch` against the old fixed string, so the
supersession ordering proof could no longer find any completion event. Every
supersession route began refusing with:

```
SUPERSESSION_EVIDENCE_INVALID: "T-8 has no canonical completion event after E-7; a DONE row alone cannot prove ordering"
```

The declared core-unit family caught it: `ran 7497, 9 new red outside the
baseline`, baseline red set empty. Those nine are the supersession and
acceptance-compaction suites — the routes that prove a later Work item really
completed before it may settle an older one.

## Why it was silent

Nothing compared the emitter to the readers. `supersession.py` was the only
consumer using `fullmatch`; every other reader is anchored loosely
(`startswith`, `search`, or `\b`) and kept working, so the breakage appeared
only where the ordering guarantee is enforced — and only in tests that exercise
a real finish. The T-1866 focused gate ran 169 tests that did not include the
supersession family.

## The fix: one owner, a closed grammar

`board.PUBLICATION_STATES` already owned the vocabulary. The suffix grammar now
sits beside it:

- `board.PUBLICATION_RELEASE_ROUTE` — the release-route sentence, spelled **once**.
- `board.PUBLICATION_SUFFIX_RE` — a **closed** alternation built from
  `PUBLICATION_STATES`, admitting exactly `; publication_state <state>` and,
  for `pending`, that one route sentence.
- `operations.finish_ticket` emits `"; " + PUBLICATION_RELEASE_ROUTE` instead of
  a private copy of the sentence.
- `supersession._COMPLETION_RE` composes the canonical phrase with
  `board.PUBLICATION_SUFFIX_RE`.

The ordering proof is unchanged: only a `DEC` event owned by the successor,
carrying the canonical completion phrase, and later than the targeted PASS,
can prove ordering. What changed is that the phrase may end with exactly one
publication decision — not with arbitrary prose.

## Evidence in this directory

| File | What it shows |
|---|---|
| `prefix-red-control.log` | The pre-fix matcher refuses the event the current writer emits; the live supersession suite goes `FAILED (failures=7)` on the pre-fix pattern and `OK` (19 tests) after restore, with the restored bytes verified identical. |

The red control is also carried inside the test suite
(`test_control_the_pre_fix_matcher_fails_this_suite`), so reverting the grammar
turns the suite red instead of the protocol going quiet.

## Tests — `tools/test_t1867_completion_grammar.py`

| Test | Claim |
|---|---|
| `test_every_emitted_completion_is_admitted` | Every event the finish writer can emit (no publication, `published`, `pending`) is admitted by the supersession matcher. `finish_ticket` refuses any phase but SHIP, so `(from SHIP)` is the only form. |
| `test_unsuffixed_completion_still_matches` | Old events and every non-`own_patch` closure keep their exact historical form. |
| `test_lookalike_suffixes_are_refused` | Seven lookalikes stay refused: an out-of-vocabulary state, an invented route, a route with no state, trailing prose, an unknown phase, and a phrase that does not open the event. |
| `test_control_the_pre_fix_matcher_fails_this_suite` | The pre-fix pattern rejects the emitted event — the fix is falsifiable, not merely permissive. |
| `test_release_route_is_spelled_once` | `operations.py` does not re-spell the route sentence; it must import the shared constant. |

## Coupled surfaces

`board` (vocabulary + grammar + route literal) → `operations` (emitter) →
`supersession` (matcher). All three now derive from the same two constants, so
adding a publication state or rewording the route cannot leave a reader behind.
