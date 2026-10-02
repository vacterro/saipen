# FUTURE GATE — REPAIR-VERB DEADLOCK: MALFORMED STATE x ILLEGAL LOG x DUPLICATE BOARD ID

Status: RECORDED FOLLOW-UP WORK / NOT AUTHORIZED FOR IMPLEMENTATION

Recorded: 2026-09-17 by an opencode session bound to `__SAITULS`
(`V:\___VAC\__K\__CODE\__SAITULS`), lineage
`lineage-ded945ae8243480ab1bfee73baeb29c6`, actor `opencode`, project
STATE `saipen_version: 7`, `schema_version: 3`, `style_contract: ded-4ae736e4`.
Installed surface under test: `C:\Users\vac34\.config\opencode\skills\saipen`
(OpenCode guard build `T-1327-zero-manual-recovery-20260914.1`).

This document is a record of an external, mechanically reproduced defect. It is
not a claim that anything here has been fixed, and it must not be cited as
evidence for any coverage disposition. Do not implement it while an active
ticket holds this repository's DOING seat.

## One-line summary

Three independent pre-existing defects — a schema-unknown STATE field, five
illegal LOG lines, and a duplicate BOARD ticket id plus stale `| blocker:`
fields on `## DONE` rows — put every sanctioned repair verb behind one of the
other defects. `recover` cannot commit (its own proposal validator vetoes the
BOARD and LOG it does not own), and `normalize-log`, the one verb that owns the
LOG lines, cannot start (its read is strictly STATE-strict while STATE carries
the field `recover` owns). No canonical action remains; the only exit is
hand-editing canonical files, the path OPS.md forbids.

## Surface state at capture (pre-repair, exact)

`__SAITULS/.saipen/STATE.md:18`

```
parked_work: "T-144 2.5.2 work consolidated in the working tree (...)"
```

`parked_work` is engine OUTPUT-only; `state.schema.json` does not define it.
`saipen validate --json` reports exactly this as its only error
(`error_count: 1`).

`__SAITULS/.saipen/BOARD.md:29` and `:39` — the same id declared twice:

```
- [ ] T-176 [P3] HUNT2: untracked one-shot probes tests/native_paste_conpty.py ...
- [x] T-176 [P1] Reliable Taskbar Edge Reveal: new standalone subsystem Scripts/taskbar_edge ...
```

`__SAITULS/.saipen/log` — five lines that do not match `LOG_RE`
(`log.py:15`):

```
LOG.md:1318   11.09.26 13:00 [E-1300] ...   (lost the leading "- ")
LOG.md:1319   11.09.26 13:01 [E-1301] ...   (lost the leading "- ")
LOG.md:1320   11.09.26 13:02 [E-1302] ...   (lost the leading "- ")
LOG.md:1322   - 2026-09-11T10:20Z SAIPATCH pause checkpoint (st): ...  (no [E-###] tag)
LOG.md:1324   11.09.26 12:11 [E-1303] ...   (lost the leading "- ")
```

`__SAITULS/.saipen/BOARD.md:38` (T-177, `## DONE`) and `:39` (T-176,
`## DONE`) both carry a trailing `| blocker: ...` field, which
`board.ticket_status_error` (`board.py:709-717`) rejects as
`carries | blocker: outside ## BLOCKED (## DONE)`.

## The deadlock — verb vs verb

```
saipen recover ... --apply-approved-repair <id>
    -> VALIDATION_FAILED: BOARD duplicate T-176; BOARD T-177 | blocker:
       outside ## BLOCKED; LOG.md:1318/1319/1320 not a legal event line

saipen recover normalize-log       (the ONLY owner of the LOG-line class)
    -> VALIDATION_FAILED: state-malformed: unknown STATE field 'parked_work'
       (STATE is read strictly; the field is owned by `recover`, which is
        itself vetoed by the LOG lines this verb would fix)

hand-editing .saipen/**            (the only remaining exit)
    -> forbidden to agents (PROTECTED_CANONICAL_NAMESPACE); operator must
       perform canonical surgery in person
```

Each verb requires a surface the other defect class has made unreadable. The
operator is walked in a circle whose only terminal move is the one path the
protocol exists to remove.

## Exact reproduction (all commands read-only or refusing; zero bytes written)

Bound project `__SAITULS`; a new actionable request had been captured as
`SRC-025` first.

```
saipen start "Execute SAITULS Secure Apps GUI closure pass ..."
  -> REFUSE [WAIT_OPERATOR]
     reason: the request is durable as SRC-025; one operator decision is open in
     this project and must be answered before new Work is projected
     next: saipen recover --apply-approved-repair f1f04ebb15577b21c0943ba86973a4374fed204c5f45fa3e2c464d38e9043b13 (operator decision)
     then: saipen start --receipt SRC-025

saipen recover --apply-approved-repair f1f04ebb... --dry-run --json
  -> ok:false  code:RECONCILE_REAUTH_REQUIRED
     STATE.blocker carries T-168 AWAITING_USER_LIVE_ACCEPTANCE with live
     ## BLOCKED board ticket(s); canonical_next_command:
     saipen recover resolve-blocker <decision>

# operator decision supplied (recorded authority text in the plan):
saipen recover resolve-blocker operator approves SRC-025 wave proceeding \
    --apply-approved-repair f1f04ebb... --json
  -> ok:false  code:VALIDATION_FAILED
     detail: proposed reconciliation fails fast validation:
       BOARD: BOARD.md:40 duplicate ticket ID T-176;
       BOARD proposed T-177 carries | blocker: outside ## BLOCKED (## DONE);
       LOG: LOG.md:1318 not a legal event line;
       LOG: LOG.md:1319 not a legal event line;
       LOG: LOG.md:1320 not a legal event line
     (the list is capped at 5; LOG.md:1322 and :1324 are also illegal)

saipen recover normalize-log --dry-run --json
  -> ok:false  code:VALIDATION_FAILED
     detail: state-malformed: unknown STATE field 'parked_work' --
       state.schema.json does not define it (retired or misspelled?)
```

Guard side, for completeness: every non-canonical shell tool on the bound
project is refused `SAIPEN_GUARD_REFUSAL: PROTOCOL_STATE_INVALID` (the
duplicate id is a `parse_board` error, so `admission.protocol_snapshot`,
`admission.py:734-747`, blocks all but `saipen_op`); direct writes into
`.saipen/**` are refused `PROTECTED_CANONICAL_NAMESPACE`. Reads, globs and
greps keep working.

## Why this is a protocol defect, not a project-data problem

1. **The proposal validator vetoes unowned pre-existing defects.**
   `reconcile_protocol_state` validates the WHOLE proposed surface
   (`reconcile.py:2068`, `fast_check.validate_texts`, `fast_check.py:431`);
   any pre-existing error — BOARD parse (`fast_check.py:542-543`), BOARD
   semantic (`:554-560`), LOG line legality (`:572`, `:70-78`) — vetoes the
   entire atomic plan (`reconcile.py:2075-2079`). The same collision was
   recorded for a different defect pair on 2026-09-16
   (`KNOWLEDGE/audits/fastprompter-reconcile-deadlock-20260916.md` and
   `future_gate/FUTURE GATE — RECONCILE DEADLOCK ON DONE-WITHOUT-VERIFY PLUS
   INVALID ACTIVE CLAIM_20260917.md`); both recommended carrying inherited
   findings the way `compact_board` already does under T-1354
   (`operations.py:4234`-era `inherited_findings`) instead of vetoing.

2. **The LOG-line repair verb read is strictly STATE-strict.**
   `normalize_log` reads with `_read(root, allow_illegal_log=True)`
   (`operations.py:6263`) and no `allow_malformed_state`, while `recover`
   itself reads with `allow_malformed_state=True` (`reconcile.py:1671`). The
   asymmetry is the wedge: the verb whose whole purpose is to be the exit from
   an unreadable LOG cannot run from the state that most needs it whenever a
   STATE-field defect coexists. Its docstring promise — "No canonical verb
   rewrote a LOG line ... This is the exit" (`operations.py:6242-6259`) —
   holds only while STATE happens to be strictly valid.

3. **Two defect classes have no repair owner at all.**
   `board_semantic_errors` recognizes `| blocker:` outside `## BLOCKED`
   (`board.py:462-520`) but no repair atom removes the field;
   `_board_lifecycle_repairs` (`reconcile.py:665`) owns only half-claim clear,
   unclaimed `## DOING` return-to-TODO, and phantom `## DONE` reopen; board
   compaction repairs only oversized rows with an `unrecognized field`
   (`board_compaction.py:874`). A duplicate ticket id is a `parse_board` error
   (`board.py:313-315`), which makes the board unaddressable by every
   operation — including the ones that could remove the duplicate. The classes
   are currently tracked only as local debt (`__SAITULS` BOARD `T-170`).

4. **Consequence.** With the checkpoint invalid, admission refuses every
   consequential tool for the whole project, so unrelated work (here: a
   Secure Apps GUI ticket, `SRC-025`) cannot start. The operator-facing
   diagnosis names `--apply-approved-repair`, a command the engine that
   printed it provably cannot commit — the CORE §1.6 "refusal that names a
   remedy no surface exposes" class.

Secondary observation: `saipen validate --json` reports only the STATE error
(`error_count: 1`) while the write-path `fast_check` sees the BOARD and LOG
defects too. Two validators disagree on the defect count of the same surface;
a diagnostic table that under-reports is how this deadlock stays invisible
until all three classes collide.

## Fix directions (analysis only; each needs its own red control)

A. **Make `normalize-log` tolerate a malformed STATE** the way `recover` does
   (`allow_malformed_state=True`, or refuse only when the STATE error is not
   one `recover` owns). The verb touches only `last_event`/`updated`/`agent`;
   the offending field is neither read nor written by it.

B. **Scope the reconciliation proposal validator** (preferred; mirrors T-1354
   and the two earlier records): carry the errors already present in the
   BEFORE surface as inherited findings in the result and the journaled
   receipt; refuse only on errors the plan INTRODUCES. The veto stays for real
   regressions; the plan stops wedging on unrelated residue.

C. **Add repair atoms for the two orphaned classes**, operator-gated like the
   phantom-DONE reopen:
   - duplicate ticket id — needs one authored policy: which record keeps the
     id (e.g. the one with allocation/build events in history), and the other
     is deterministically renumbered to the next free id (never deleted),
     with original bytes archived as recovery evidence;
   - stale `blocker`/`blocker_scope` on a non-`## BLOCKED` row — mechanical
     removal of the field, same shape as `_state_blocker_repairs`.

D. **A single bounded, closed multi-surface repair set** that can span
   STATE + BOARD + LOG when no individual verb can proceed, so independent
   verbs never depend on surfaces the other defect class has made unreadable.

Required hostile controls:

- A fixture carrying all four defects (schema-unknown STATE field, bulletless
  LOG lines, duplicate BOARD id, `| blocker:` on a `## DONE` row) reaches
  `REPAIRED`/`REPAIR_REQUIRED` through named commands only, with no hand
  edits; a red control on the current code reproduces the two-leg circle
  above exactly.
- `recover normalize-log` runs on a malformed STATE whose error `recover`
  owns, and refuses (structured code, no traceback) when it does not.
- The duplicate-id policy is deterministic and operator-gated: live Work is
  never auto-deleted, the id that keeps its identity is chosen by recorded
  history, and both original bytes survive as recovery evidence.
- The proposal validator still refuses errors the plan INTRODUCES; carried
  errors are reported, never silently normalized; no evidence is fabricated.

NON-GOALS: do not weaken the STATE schema, the LOG grammar, ticket identity,
or the `## DONE requires | verify:` invariant; do not add a generic
"unblock anything" verb; do not advise manual canonical-file edits — the
whole point is that protocol state changes through operations. This incident
is the measured cost of that rule having no engine exit.

## Minimal repro

```
mkdir scratch/.saipen
# STATE.md: add a schema-unknown field, e.g. `parked_work: "x"`
# LOG.md:   append  `11.09.26 13:00 [E-001] [agent: a] RUN: x`   (NO leading "- ")
#          append  `- 2026-09-11T10:20Z free-text note`           (no [E-###])
# BOARD.md:
#   ## TODO
#   - [ ] T-2 [P1] second use of an id already declared under ## DONE
#   ## DONE
#   - [x] T-2 [P1] first use ... | verify: y | blocker: stale advisory field

saipen validate --json                     # 1 error: parked_work (under-reports)
saipen recover --apply-approved-repair <id>
    # VALIDATION_FAILED: duplicate id + | blocker: + LOG lines (first 5 errors)
saipen recover normalize-log               # VALIDATION_FAILED: parked_work
# no third canonical move exists
```

## Originating mission

Operator handoff `SAITULS_20260917_2301.md` (Secure Apps GUI closure pass,
phases 0-16), delivered to the bound `__SAITULS` session and captured as
ingress receipt `SRC-025`. The session could not start the requested work
because the project's canonical surface is in the above deadlock; zero
canonical bytes were written by the engine, and all code surfaces of the
requested ticket are untouched. The fix belongs to the SAIPEN protocol tree —
a different repository than the bound project — so this record is the
cross-project handoff rather than an edit of unrelated protocol code.

Related records:

- `KNOWLEDGE/audits/fastprompter-reconcile-deadlock-20260916.md` — same
  family: unowned pre-existing BOARD error vetoes the whole plan.
- `future_gate/FUTURE GATE — RECONCILE DEADLOCK ON DONE-WITHOUT-VERIFY PLUS
  INVALID ACTIVE CLAIM_20260917.md` — same family, second defect pair.
- `__SAITULS` BOARD `T-170` — local debt entry for the same surface classes.
- T-1356 (`normalize_log`) and T-1324 (`_state_blocker_repairs`) — the two
  existing exit verbs this deadlock wedges.
