# T-1862 / SRC-294 — project readiness is not the execution phase

FINAL OUTPUT for the SAIHANDOFF "SAIPEN / PROJECT COMPLETION SEMANTICS /
AUDIT DEBT VISIBILITY". Every claim below has a command in this directory.

## ROOT_CAUSE

`saipen status` published ONE lifecycle verdict — `phase` and `task` from
STATE — and nothing else that could describe an outstanding obligation.
`phase: DONE` is the correct verdict for the last *execution* ticket, so the
payload was not lying; it was incomplete. The human renderer printed the same
single verdict, so `phase: DONE` was the only reading available and an operator
naturally read it as *project* completion.

Measured on the real SAITULS project before any change (read-only):
`phase DONE`, `task none`, `top_workable_ticket: null`, while BOARD carried
1 DOING / 2 TODO / 207 DONE / 7 BLOCKED and coverage held 230 requirements
with 162 UNKNOWN. Nothing in `status --json` named any of that.

Confirmed on the disposable fixture before mutation: the pre-change
`status --json` had no readiness key at all (see `SCOUT-SYMBOLS.md`).

## CHANGED_SYMBOLS

| symbol | file | change |
|---|---|---|
| `readiness.derive` | `tools/saipen_engine/readiness.py` (new) | pure derivation of six dimensions + one precedence-derived status; no I/O, no writes, no authority |
| `readiness.STATUSES` / `HEADLINES` / `SCHEMA_VERSION` / `RULE_ID` | same | the closed vocabulary and its human headlines |
| `_status` | `tools/saipen.py` | captures the inbox status it already computed (`_status_inbox`), derives coverage per active receipt and orphan state read-only, and projects `payload["readiness"]` |
| `_emit` | `tools/saipen.py` | prints `Readiness: <STATUS> -- <headline>`, up to four reasons, and the QUOTED authority; renders nothing for `--json` |

`phase`, `task`, `continuation_authority`, `safety_valve_mode`,
`goal_authority` and every existing payload key are unchanged in name, value
and meaning. `readiness` is additive.

## NEW_STATUS_CONTRACT

`readiness` object, `schema_version: 1`, `rule_id: "T-1862"`:

```
status         one of EXECUTION_IDLE | WORK_AVAILABLE | WORK_BLOCKED |
               EXTERNALLY_BLOCKED | AUDIT_OUTSTANDING |
               SOURCE_RECONCILIATION_REQUIRED | INTEGRITY_BLOCKED |
               PROJECT_ACCEPTED | UNKNOWN (projection failed)
headline       the one-line human reading of `status`
accepted       status == PROJECT_ACCEPTED
ready          alias of `accepted` (kept explicit: "ready" reads as permission)
reasons        why this status won, in precedence order
execution      {phase, task, terminal_phase, claimed_ticket} — QUOTED
dimensions     {work, audit, source, integrity, authority}
grants_authority   always false
authority_unchanged always true
```

Precedence, highest first: INTEGRITY_BLOCKED → AUDIT_OUTSTANDING (pending
layers) → SOURCE_RECONCILIATION_REQUIRED → AUDIT_OUTSTANDING (invalid layers)
→ WORK_AVAILABLE (runnable, then claimed) → EXTERNALLY_BLOCKED / WORK_BLOCKED
→ PROJECT_ACCEPTED → EXECUTION_IDLE.

`status` is computed at read time from facts already on disk. No durable
history is rewritten, no field is renamed, and no consumer that ignores
`readiness` changes behaviour.

## NEGATIVE_REGRESSION

The matrix is `tools/test_t1862_readiness.py`, classes A–L, 20 tests, all green
(`matrix.log`). Each letter is asserted against a synthetic input, not against
prose:

- **A** all terminal, no work → `PROJECT_ACCEPTED`
- **B** DONE + unconsumed audit layer → `AUDIT_OUTSTANDING`, not accepted
- **C** DONE + 162 non-terminal clauses → `SOURCE_RECONCILIATION_REQUIRED`
- **D** DONE + only external blockers → `EXTERNALLY_BLOCKED`
- **E** operator-paused security ticket → visible as claimed/runnable state,
  never auto-admitted; readiness reports a status and grants nothing
- **F** audit consumed + valid receipt → no false reopening
- **G** audit body missing, contract intact → blocker retained
- **H** duplicate archive/active references → counted once
- **I** invalid records → no fake coverage
- **J** fresh authorization absent → status reporting cannot reset authority
- **K** cross-project `status` → STATE/BOARD/LOG bytes identical before/after,
  and the human and machine answers name the same status
- **L** historical claims without evidence → readiness stays qualified

Two defects were caught by this matrix inside the fix itself, and both are
recorded in the module: (1) `open` originally counted only DOING+TODO, so an
all-blocked project reported `PROJECT_ACCEPTED` — the very defect under repair;
(2) a claimed DOING ticket was reported `WORK_BLOCKED`. Both are now covered by
tests.

A third was found in REVIEW and closed with its own red-before-green pair. The
readiness derivation treated an unreadable intake index as an empty one:
`_status` caught the read failure, substituted `{}`, and `_source_dimension`
then reported zero requirements and zero outstanding — "no known obligation"
read as "no obligation". A project whose source records were corrupt could
therefore satisfy `PROJECT_ACCEPTED`. `receipts` is now `Optional`; `None`
means unreadable and yields `receipts_known: False` plus `INTEGRITY_BLOCKED`
before any count is read as zero, while `[]` keeps meaning "read, and there is
nothing". Executed control: the staged pre-fix module makes
`test_unreadable_coverage_is_not_empty_coverage` FAIL (`True is not false`);
the fixed module passes.

A second REVIEW inspection of the current revision found the same failure
class on two other inputs. `audit_inbox.status` can return `ok: false` without
pending layers, or raise so `_status_inbox` is `None`; `recover_orphans` can
raise so `_orphans` is `None`. The derivation formerly treated those unknown
reads as zero debt and could emit `PROJECT_ACCEPTED`. It now refuses acceptance:
an unknown or failed orphan diagnostic yields `INTEGRITY_BLOCKED`, while an
unknown or failed audit classification yields `AUDIT_OUTSTANDING`. Audit residue
and an unclean inbox also remain outstanding. Four new focused cases cover
these routes; the existing cases for unknown inputs now assert the safe result.
The A-L matrix plus these edge cases contains 26 tests.

Current revision verification: `python -B tools/core_unit.py focused T-1862
--pattern test_t1862_readiness.py` PASS 26, fresh record
`.saipen/evidence/focused-unit/f49e39231a394410-20261023T133502251186Z.json`;
`python -B tools/fixture_t1862_saituls_shape.py` FIXTURE HOLDS;
`python -B tools/control_t1862_display.py` CONTROL HOLDS;
`python -m ruff check tools/saipen_engine/readiness.py
tools/test_t1862_readiness.py` passed. The revised oracle explicitly rejects
unknown audit and orphan diagnostics; acceptance is tested only with known,
clean inputs.

REVIEW of this revision: inspected the changed branches in `_audit_dimension`,
`_integrity_dimension`, and `derive` against `_status`'s actual failure outputs
and the direct consumer's human display. Unknown diagnostics cannot enter the
`PROJECT_ACCEPTED` branch; known clean inputs still can. The current oracle
fails five assertions on the staged pre-fix subject via
`python -B .saipen/evidence/T-1862-readiness/red-unknown-control.py` and passes
on the working subject. Independent fresh REVIEW run: focused 26 PASS,
record `.saipen/evidence/focused-unit/f49e39231a394410-20261023T133820097702Z.json`;
display control HOLDS. No further finding in the owned delta; no reusable
memory card warranted.

Publication-family check after that REVIEW exposed one new red in this ticket's
own proof scripts: `test_subprocess_utf8.SubprocessUtf8Contract.test_no_production_text_call_uses_the_implicit_locale`
named two `subprocess.run(text=True)` sites in `tools/control_t1862_display.py`
and one in `tools/fixture_t1862_saituls_shape.py`. Full run: 7459 tests,
1 new red, record `.saipen/evidence/core-unit/f49e39231a394410-20261023T141204831560Z.json`.
All three now specify `encoding="utf-8"`; the exact formerly red test passes,
the display control still HOLDS, the disposable fixture still HOLDS, and ruff
passes on both edited files. No production readiness behavior changed in this
correction. A new full-family run on the final bytes is still required.

## BACKWARD_COMPATIBILITY

- No existing key removed or renamed; `phase` keeps its exact meaning.
- No STATE/BOARD/LOG schema change, no migration, no journal entry.
- `readiness` is absent from every non-`status` verb.
- A consumer that never reads `readiness` sees a byte-identical payload shape
  plus one extra key.
- The projection is wrapped: a derivation failure yields
  `status: UNKNOWN`, `accepted: false`, with the exception named in `reasons`,
  never a green status and never acceptance.

Cost: `status --json` median moved 13.92 s → 15.79 s in a randomized
interleaved benchmark (4 runs each); the aggregates themselves measure 0.49 s
(index 0.01, 194 receipts 0.13, orphans 0.35). The remainder is filesystem
noise on this volume, not a second project walk.

## SAFETY_VALVE_PRESERVATION

- `continuation_authority`, `authority_source`, `authority_until`,
  `safety_valve_mode` and a `WAIT:` `next_action` are copied verbatim into
  `dimensions.authority` and never re-decided.
- `grants_authority` is hard-coded `False`; `authority_unchanged` `True`.
- A new audit layer or a fresh UNKNOWN clause raises `status` only. It does not
  raise the valve, open a wave, mint an ingress, or change any authority field.
- No blocked ticket becomes runnable: `WORK_BLOCKED` and `EXTERNALLY_BLOCKED`
  are separate terminal readings and the router still refuses them.
- Matrix J and the live run both show `operator_required` / `hard_wait`
  unchanged while the derived status is `AUDIT_OUTSTANDING`.

## SAITULS_FIXTURE_RESULT

`tools/fixture_t1862_saituls_shape.py` builds a DISPOSABLE project with the
reported shape (DONE / task none / `operator_required` / `hard_wait`, 1 audit
layer, 162 UNKNOWN clauses on SRC-001, 7 BLOCKED_EXTERNAL tickets, 2 TODO) and
asserts the contract end to end (`fixture.log`):

```
execution_phase: DONE
execution_task: none
derived_status: AUDIT_OUTSTANDING
accepted: False / ready: False
reasons: ['1 audit layer(s) not consumed']
work: doing 0, todo 2, done 1, blocked 7
source: 1 receipt, 162 requirements, 162 outstanding
authority: operator_required + hard_wait
grants_authority: False
memory_unchanged: True
FIXTURE HOLDS
```

Removing the audit layer from the same fixture flips the derived status to
`SOURCE_RECONCILIATION_REQUIRED` with `162 actionable source clause(s) not
terminal`, so the two obligations are independently observable.

The real SAITULS project was read only; `No unauthorized SAITULS source
mutation occurs.` Its STATE also moved under another seat during this ticket
(BUILD/T-316 → REVIEW/T-316) without any write from here.

## NEXT_ACTION

Live, on this repository, the new surface already reports the debt the old one
hid:

```
Readiness: AUDIT_OUTSTANDING -- an audit layer is waiting to be consumed
  9 audit layer(s) not consumed
  authority unchanged: continuation_authority=operator_required safety_valve_mode=hard_wait
```

`saipen validate` remains FAIL (23 problems) and none of them is produced by
this change: 1 `EX-000022` closure-provenance failure (installed engine
generation moved) and 22 untracked-in-HEAD runtime manifest entries owned by
other tickets. The three files added here are staged so they are no longer part
of that list.
