# T-1883 / SRC-308 — P0 RECONCILIATION SELF-DEADLOCK: result

Eleven required keys, in the handoff's order. Every claim below is tied to a
file in this directory or to a named command with its measured output.

---

## ROOT_CAUSE

`tools/saipen_engine/reconcile.py::_state_blocker_repairs` decided whether a
non-empty `STATE.blocker` in an ACTIVE phase was *provably stale* by asking
whether the BOARD held ANY ticket in `## BLOCKED`:

```python
if live_blocked or cls is not None:      # pre-fix, line 352 of both runtimes
```

`live_blocked` was the whole `## BLOCKED` section, sorted, with no relation to
`STATE.task`. So the presence of a parked ticket anywhere on the project
became authority over every later independent ticket. That is substitution of
project inventory for causality.

Measured, two STATEs identical down to the byte except BOARD inventory
(`e2e-repro.log`, scenario A vs B):

| BOARD `## BLOCKED` | BEFORE verdict |
|---|---|
| none | `ok: true`, `REPAIRED`, blocker → `none` |
| T-1469, T-1480, T-1483, T-1505 (unrelated) | `ok: false`, `RECONCILE_REAUTH_REQUIRED`, `refuse: true` |

The blocker text and its evidence were the same in both runs. The only input
that changed was the count of unrelated tickets.

Secondary cause, the one that made it self-deadlocking: a normal transition
never writes `STATE.blocker`. `_plan_transition` (`operations.py:4489`) builds
its owned-field set as `{phase, next_action, transition_from, last_event,
updated, agent}`. Only a direct `patch_state` caller can create a blocker, so
an agent typing one produces state that no canonical verb authored — and then
`binding_brake` treats it as an unresolved operator gate for every subsequent
tool.

## EXACT_CODE_CHANGES

`tools/saipen_engine/reconcile.py`

- `_state_blocker_repairs`: replaced the presence test with
  `if cls is not None or related:` where `related` comes from a causal
  classifier. The `if cls is not None:` shortcut the handoff explicitly warned
  against was NOT taken: a blocker that is causally owned by a blocked ticket
  still refuses even when its text carries no recognised class token.
- New `_causally_related_blocks(task, live_blocked, tickets, blocker) ->
  (related, unrelated)`. Relation comes only from parsed identifiers:
  `STATE.task` is the active ticket; a blocked ticket whose `needs` names the
  active ticket; the active ticket's `needs` naming a blocked ticket; or the
  blocker text naming a blocked ticket id as a bounded token.
- New `_ids_in(text) -> set[str]` using `\bT-\d+\b`, so `T-1` never matches
  `T-10`.
- An empty or `none` `task` relates to nothing, so the empty case cannot
  resurrect presence-based vetoing.
- Each repair now carries a `classification`: `SAFE_CANONICAL_REPAIR`,
  `RELATED_ACTIVE_GATE`, or `GENUINE_OPERATOR_DECISION_REQUIRED`. The existing
  repair-dict contract is unchanged otherwise — no second framework.
- The refusal reason names the unrelated tickets it declined to be vetoed by,
  so the operator can see why the refusal is not about them.
- Docstring states the incident, the measured A/B, and the closed relation
  sources.

`tools/test_recovery_reachability.py`

- `test_a_live_board_block_refuses` — the over-broad expectation the handoff
  required replacing — became `test_a_related_live_board_block_refuses`: a
  board where T-001 sits in `## BLOCKED` and needs T-000 while T-000 is DOING.
  It still asserts `refuse` and that the reason names T-001, so the legitimate
  security coverage is retained at its original site.
- Added `test_an_unrelated_board_block_does_not_refuse`.

`tools/test_t1883_reconcile_causality.py` (new, 17 tests)

- AC-01..AC-04: unrelated blocks of count 0, 1, 4 and 100 leave the verdict
  identical.
- AC-05: all three relation directions plus the recognised-class case still
  refuse, with the parallel test proving a class token refuses amid unrelated
  blocks.
- AC-06: a ticketless state relates to nothing; token bounds hold; an
  unproven relation is reported, never trusted.
- `EndToEndVerdictTests`: the same three cases through
  `reconcile_protocol_state` — the single verdict owner behind `cc`, `recover`,
  `status` and Fleet — with byte-level write assertions.
- `AC_COVERAGE` names the module owning each criterion delegated to other
  Work, with a test that fails if a mapping points at a non-existent file.

## REPRODUCTION_BEFORE

`e2e-repro.log`, BEFORE column. Both installed runtimes still carry the defect
(`tools/saipen_engine/reconcile.py` line 352 in runtimes `76a5995cbf99aacc`
and `d838d464759d97d3`, `_causally_related_blocks` count 0), so the pre-fix
bytes are not hypothetical — they are the bytes the operator is running.

Scenario B wrote zero bytes and returned
`RECONCILE_REAUTH_REQUIRED` / `remediation: OPERATOR_DECISION`.

## REPRODUCTION_AFTER

`e2e-repro.log`, AFTER column, four verdicts:

- BEFORE the defect reproduces: HELD
- AFTER unrelated blocks change nothing: HELD
- AFTER the incident blocker is repairably stale: HELD (`ok: true`,
  `REPAIRED`, blocker → `none`, unrelated tickets untouched)
- AFTER a causally related block STILL refuses: HELD

## REGRESSION_RESULTS

Focused gate, 9 reconcile-related modules, at tree fingerprint
`646179cb8997368d`:

```
python -B tools/core_unit.py focused T-1883 --pattern test_t1883_reconcile_causality.py
  --pattern test_recovery_reachability.py --pattern test_reconcile_valve.py
  --pattern test_t1751_reconcile_surfaces.py
  --pattern test_reconcile_history_ledger_blocked.py
  --pattern test_reconcile_legacy_output_field.py --pattern test_improve_reconcile.py
  --pattern test_next_action_deadlock.py --pattern test_recover_approved_repair.py
  --timeout 290
=> {"ok": true, "verdict": "PASS", "ran": 189, "duration_s": 227.875,
    "record": ".saipen/evidence/focused-unit/646179cb8997368d-20261024T144829783915Z.json"}
```

Record sha256 `096a68cfa877df6fd8ae474d5826a0748dba19a676ea78718057bee750532a9e`.

`red-control.log`: the SAME test bytes against a copy with only the presence
veto restored — 8/8 expected-red tests fail, all five related-gate/class-token
security tests stay green, no unexpected failure. The control bites for its own
reason.

Not run: the complete core-unit family. T-1882 measured it at 7576 ran / 55 red,
all 55 foreign (six modules calling a release API the source does not carry;
three docs-coverage reds). `tools/core_unit_baseline.json` holds red 0 and
editing it is forbidden, so a full-family PASS is not obtainable from this tree
for reasons outside this ticket. Focused proof is what
`tools/verification_policy.json` (`ticket: focused`) admits to SHIP; it does not
admit publication.

## AUTHORITY_INVARIANTS

Still refusing after the repair, each with its own test:

1. A blocked ticket the active work needs.
2. A blocked ticket that needs the active work.
3. A blocker whose text names a live blocked ticket.
4. A recognised gate class token (`HELD`, `BLOCKED_EXTERNAL`,
   `WAIT_USER_CONFIRMATION`, `WAIT_ROLE:<role>`, ...) — refuses even amid
   unrelated blocks, classified `GENUINE_OPERATOR_DECISION_REQUIRED`.
5. `phase: BLOCKED` retains its blocker (no repair path at all).
6. An out-of-enum phase refuses rather than clearing the blocker.
7. Publication authority is not modeled by this classifier and was not
   touched: the phase-transition gate and the external-publication gate remain
   distinct, per B05.
8. Nothing here manufactures authorisation. The repair writes `blocker: none`,
   the original STATE bytes are archived under
   `.saipen/recovery/`, and it never writes LOG authority, never increments a
   counter and never rewrites history.

The repair cannot fabricate a transition: a blocked ticket is only consulted
for whether it governs, never for whether the transition committed.

## CANONICAL_REPAIR_EVIDENCE

- Idempotent by construction: after the repair the blocker is `none`, and the
  function returns `[]` for an empty/`none` blocker on its first guard.
- Byte-safety: the end-to-end tests assert `changed.board == []` for the
  incident shape, i.e. no unrelated ticket is unblocked or rewritten.
- Crash-safety comes from the existing reconcile pipeline, not from new code:
  repairs are applied through the canonical writer, which archives the
  pre-image under `.saipen/recovery/state-legacy-output/` (observed in the E2E
  run's `targets` list), and the CAS/ledger path is unchanged.
- No direct `STATE` overwrite was added, no LOG line was fabricated, no
  counter was touched.

## DEPLOYMENT_PARITY

**INCOMPLETE.** Source `reconcile.py` is 3842 lines, sha256 `5379166af65017af…`;
both installed runtimes are 3763 lines, sha256 `3055495a4303dada…`, and both
still contain `if live_blocked or cls is not None:` and zero occurrences of
`_causally_related_blocks`. The repair exists in the source tree only. Until
the runtime is rebuilt, an operator running the installed `saipen` still hits
the original deadlock.

## FASTPROMPTER_INCIDENT_STATUS

**NOT VERIFIED / PENDING.** The real FastPrompter project state was not
available to this session, so live acceptance was not attempted. What is
proven is the isolated engine repair, on fixtures reproducing the reported
shape: SHIP phase, `task: T-1517`, blocker
`operator_required (continuation_authority) for REVIEW -> SHIP`, four unrelated
blocked tickets. Under those exact inputs the repair is now automatic and the
unrelated tickets are untouched. Claiming the real incident recovered would
require its actual STATE and BOARD.

## REMAINING_GENUINE_GATES

- Runtime rebuild: the fix is not deployed (above). This is a real gate, not a
  diagnostic.
- Live FastPrompter acceptance: needs the real project bytes.
- Publication: T-1883 is in SHIP, and the SHIP phase's publication path
  requires a full core-unit PASS for the exact bytes. The tree carries 55
  foreign reds and a `red 0` baseline, so publication stays blocked on the
  foreign batch — the same blocker T-1879 and T-1882 recorded. Focused proof
  admits SHIP, never publication.
- P1 Auto-Doctor extension after a refusal was deliberately not bundled here:
  it widens the write surface of the doctor, and the handoff's priority order
  puts the P0 classifier first. It remains open work.
- T-1827 (writer lock) and T-1882 remain as recorded: T-1882's evidence is
  durable in `.saipen/evidence/T-1882-regression-baseline/`.

## NEXT_EXACT_ACTION

Rebuild the installed runtime from this source, then re-run the E2E fixture
against the deployed `saipen` binary rather than the source tree:

```
python tools/saipen.py version --json          # confirm deployed identity
saipen recover --json                          # on a copy of the incident project
```

Expected after deploy: `REPAIRED` on the incident shape, `RECONCILE_REAUTH_REQUIRED`
only for a causally related or recognised-class gate.

---

## CORRECTION (same session, after T-1883 closed)

The `_incident_project` fixture in `tools/test_t1883_reconcile_causality.py`
built `## BLOCKED` rows without the `| blocker:` field that BOARD lifecycle
requires. `reconcile_protocol_state` still returned the right blocker verdict
on them — which is why the 17 tests passed — but the proposed board then failed
fast validation in the full `cc` path, so the fixture was not exercising a
board-valid project end to end. Found by driving `saipen continue` on it: the
blocker was correctly cleared, but the run then refused on BOARD semantics.

Fixed by adding `| blocker: vendor ack pending | blocker_scope: ticket` to each
fixture row. Re-measured after the fix:

- `tools/test_t1883_reconcile_causality.py`: 17/17 OK.
- `e2e-repro.log`: all four verdicts still HELD, scenario B now writes STATE
  and LOG normally (a real repair rather than a repair blocked downstream).
- `saipen continue` on the incident shape: reconciliation `REPAIRED`, blocker
  cleared, and the run then reports the next genuine gate —
  `INCOMPLETE_TICKET: finish requires explicit verification evidence for ticket
  T-1517` with its exact `checkpoint RUN` command. That is D03/D04/D06/D15/D16
  behaving as the handoff requires: the machine-repairable defect is repaired
  without asking the operator, and the remaining refusal is a real gate with a
  precise action.

This edit moved the tree fingerprint after T-1883 had already closed, so its
SHIP citation (`646179cb…`) no longer describes HEAD's bytes. A fresh focused
run at the corrected tree passed 175 tests and produced
`.saipen/evidence/focused-unit/e8e20c851d3f8055-20261024T151820886439Z.json`,
sha256 `34f20abfd0ef880d0d07dcc9184b4552d409e2ca8c3e9bba6be1f8e231335223`,
fingerprint `e8e20c851d3f8055`. The source fix itself was not touched: 
`reconcile.py` still hashes `5379166af65017af…` and carries
`_causally_related_blocks`.
