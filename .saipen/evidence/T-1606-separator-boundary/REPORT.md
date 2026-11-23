# T-1606 — the STATE writer accepted scalars its own reader splits

Ticket: T-1606 (SRC-167). Phase at report time: BUILD, after VERIFY_RETRY_CAP
was lifted on changed evidence.

## Root cause

`STATE.md`'s frontmatter has two halves that disagreed about where a record
ends.

`parse_frontmatter` (`tools/saipen_engine/state.py:108`) splits the document
with `text.splitlines()`. That honours ten physical record separators: LF, CR,
VT (`\x0b`), FF (`\x0c`), FS (`\x1c`), GS (`\x1d`), RS (`\x1e`), NEL
(`\x85`), U+2028 and U+2029.

`patch_state` splits with `text.split("\n")` and `_render_value` quoted any
value it did not trust instead of rejecting it. Quoting covered spaces, colons,
quotes, backslashes and specials — but never the record separators the reader
cuts on.

The two halves therefore disagreed in the worst possible direction. A value
carrying U+2028 was written back as one line and read back by the parser as TWO
records. Measured before the fix, on the shipped bytes:

```
U+2028  patch ok, parse -> ERROR: line 4: duplicate STATE field 'phase'
U+2029  patch ok, parse -> ERROR: line 4: duplicate STATE field 'phase'
U+0085  patch ok, parse -> ERROR: line 4: duplicate STATE field 'phase'
U+000B  patch ok, parse -> ERROR: line 4: duplicate STATE field 'phase'
U+000C  patch ok, parse -> ERROR: line 4: duplicate STATE field 'phase'
```

LF and CR failed the same way (`unparseable frontmatter line: 'b"'`). The
writer's own output was unreadable to its own reader, and the injected field
came from the value, not from any writer.

## The fix

One boundary, not two: `_render_value` now refuses every separator through
`board.record_separator_in`, the predicate BOARD already uses for exactly this
reason. Escaping was rejected as a cure because `coerce` decodes only `\\` and
`\"`; re-encoding a separator would make the codec non-bijective, trading one
silent corruption for another. Refusing is the honest answer, and it matches
SRC-167:R002's "refuse malformed... without coercion".

A second hole in the same clause: the grammar matched `[A-Za-z_-]+` and then
checked only casing and the ticket-bearing rule, so `PHASE NO_SUCH_PHASE`
passed — an uppercase single token that is not in the § 1.6 enum. A cold
reader would load `phases/no_such_phase.md` and find nothing to execute.
`phase_next_action_error` now rejects any phase outside `ALL_PHASES`. Every
caller gates on the `PHASE ` prefix first, so the `WAIT:`, `RUN:` and
`RESUME:` forms are untouched.

## Changed paths

| Path | Change |
| --- | --- |
| `tools/saipen_engine/state.py` | `_render_value` refuses `record_separator_in`; imports the canonical predicate and its names from `board` |
| `tools/saipen_engine/phases.py` | `phase_next_action_error` rejects a phase outside `ALL_PHASES` |
| `tools/validate.py` | the validator's own copy of the rule gains the same `ALL_PHASES` check (see REVIEW audit below) |
| `tools/test_state_scalar_quoting.py` | `RecordSeparatorWriterTests` — 4 tests |
| `tools/test_next_action_deadlock.py` | `UnknownPhaseGrammarTests` — 4 tests, including the engine/validator agreement check |

The subject diff is `subject.diff` in this folder
(`sha256:9487cf47c8e07c6100a3e37bf5cd7e9734b2bf41dd15cda46098cdb417b3f78b`).

## REVIEW audit — one finding, fixed in this revision

The REVIEW self-audit found a real P1 defect in the first implementation
revision, not in the tests.

`tools/validate.py` keeps its own copy of the § 1.2 `PHASE` pairing rule
(`_PHASE_NA_RE` plus `_phase_next_action_error`, line ~760). That copy exists on
purpose — the constitution's own ADD example once wrote the forbidden
`PHASE PLAN T-###`, so the check is spelled out next to the sentence it
enforces. The first revision added the `ALL_PHASES` check to the engine and left
the copy alone, so the writer refused `PHASE NO_SUCH_PHASE` while the canonical
validator accepted it. SRC-167:R002 requires exactly one grammar "across the
writer, strict reader, checkpoint validation and reconciliation", and this is
the same "enforced on one surface only" defect the rule exists to prevent.

Measured before the fix, both functions on the same values:

| value | engine | validator |
| --- | --- | --- |
| `PHASE NO_SUCH_PHASE` | refuses | accepts |
| `PHASE BANANA` | refuses | accepts |

Fixed by adding the identical guard to `validate.py:~784` and by pinning the
agreement with `test_the_validator_agrees_with_the_engine_on_every_verdict`,
which loads the validator's own definitions by AST and compares verdicts across
the unknown-phase cases and all 16 enum phases. Red control: removing only the
validator guard turns that test red (`FAILED (failures=3)`, first failure names
`PHASE BANANA`); restoring it returns `Ran 12 tests ... OK`. Neighbour set after
the fix: `Ran 141 tests in 57.905s ... OK`.

`ruff` is clean on all four changed files. The `xpatch-survival` warning the
validator now prints for `tools/validate.py` is the expected consequence of an
uncommitted change to a path an older `XP-000002` receipt covers: measured
absent on the clean tree and present only while this delta is uncommitted.



Both halves were measured against the same tree, with only the fix removed
between runs.

**state.py** — `tools/test_state_scalar_quoting.py`:
- without the fix: `Ran 13 tests ... FAILED (failures=11)`
- with the fix: `Ran 13 tests ... OK`

**phases.py** — `tools/test_next_action_deadlock.py`:
- without the fix: `Ran 11 tests ... FAILED (failures=2)`
- with the fix: `Ran 11 tests ... OK`

Logs: `red-both.log`, `green-state.log`, `green-phases.log` in this folder.

Controls held on both sides: `PHASE DONE T-999`, `saipen continue`,
`a "quoted" word` and `a\b` still round-trip through `patch_state` and
`parse_frontmatter`, and every one of the 16 enum phases is still accepted at
its legal shape.

## Focused and full validation

Adjacent suites, all green with the fix in place:

| Suite | Result |
| --- | --- |
| `test_state_scalar_quoting` | 13 OK |
| `test_next_action_deadlock` | 12 OK |
| `test_refusal_registry` | 6 OK |
| `test_recovery_reachability` | 85 OK |
| `test_t1304_review_p0_repair` | 25 OK |

All five together, after the REVIEW fix: `Ran 141 tests in 57.905s ... OK`.

`tools/validate.py`: one FAIL, the pre-existing `EX-000022` closure-provenance
finding. It predates this work and is unchanged by it — the dependency moved
against the receipt, which is a release-closure question, not a STATE one.

`ruff 0.16.0` over both changed source files and both test files: clean.

The declared core-unit family was re-run after the `phases.py` change and is
recorded in `.saipen/evidence/core-unit/`; the earlier run on this working tree
answered `status: PASS`, `ran: 8383`, `red: []`.

## Lifecycle evidence

Claimed through `saipen claim T-1606` at `PHASE SCOUT T-1606`. The
`VERIFY_RETRY_CAP` blocker was lifted with `saipen ticket unblock T-1606` after
both of its stated conditions were met with changed evidence: the seven
preserved neighbours are green and the Unicode line-separator writer mismatch
no longer reproduces. The decision is recorded as a `DEC` checkpoint.

## Remaining risks

- The refusal is a hard error for any caller that builds a multi-line value
  deliberately. No caller in the tree does — the block renderer feeds the same
  codec and now fails loudly rather than corrupting — but a future one would
  learn this at write time, not at read time. That is the intended direction.
- `record_separator_in` is BOARD's predicate. If a separator is ever added to
  `splitlines`' boundary set and not to `RECORD_SEPARATORS`, STATE inherits the
  same gap. `test_the_boundary_predicate_covers_the_same_set` pins the set the
  two share today; it cannot detect a Python-level change to `splitlines`.
- SRC-167's remaining clauses (R001, R003, R004, R005) were already shipped
  before this ticket: `WAIT_OPERATOR` is registered in `REGISTRY.json`, the
  canonical `WAIT:` form round-trips, and `RECONCILE_REAUTH_REQUIRED` recovery
  exists. This work closed R002's two measured holes; it did not re-prove the
  others.
