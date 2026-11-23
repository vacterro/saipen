# T-1637 coherence audit (SRC-186)

Request: "improve this protocol to the end so that it is whole and logical".
Measured 2026-10-06 on the working tree after T-1626 (validator `--gate core`
findings JSON, engine source, protocol documents, BOARD/LOG). Each class names
where two parts of the protocol disagree, why it matters, and the repair.

A protocol is coherent here when (1) every rule has one owner and its
self-checks read that owner, (2) every machine fact has one source, (3) every
WARN is actionable by a named route, and (4) every stated limit is either
enforced or not stated.

## C1 Self-checks contradict or miss the law they guard (validator drift pins)

`--gate core` emits 11 distinct `cross-doc-drift` warnings on every run.

- Rule present, pin stale (compaction moved the wording; the substring pin
  never followed): ahead-stamp-repair (CORE 1.11 "Prevent future-stamp
  deadlock"), shortcut-memory-ban 1.10 (CORE 1.10 "Prevent shortcut invention
  ... Recall is not authority"), command-not-dropped (CORE 1.11 "Prevent lost
  deferred commands"), plan-goal-pair (CORE 1.10 "Proposal exception"),
  permanent-owner-section (CORE 1.2 "A permanently unsatisfiable ticket ...
  stays BLOCKED"), package-handoffs CORE ("Refusal changes no project file,
  checkpoint, Git ref or remote"), shortcut-rationale.
- Rule present, pin blind to line wrap/emphasis: package-handoffs
  phases/translate.md:90 ("**No ready handoff means no main\nwrite.**").
- Pin demands what the law forbids: ticket-fields, ticket-bearing, any-from.
  CORE 1.2 says the closed ticket-field list "is owned by REGISTRY.json ... Do
  not duplicate it in prose"; CORE preamble says "Prose is never a runtime
  database". The validator warns because CORE does not enumerate those sets,
  and `phases.py:38,41` already derives ANY_FROM / TICKET_BEARING_PHASES from
  REGISTRY, so the pin compares REGISTRY with itself through prose that must
  not exist.
- Every message says "RFC" / "RFC.md"; RFC.md is a 260-byte redirect stub and
  `_read_rfc` actually reads CORE.md + MAINTENANCE.md.
- tools/audit_checks.py `_W4_RETIRED_PROSE_CONTROLS` (b23019f4, 2026-08-31)
  retired the mutation controls of these pins when CORE was compacted, while
  validate.py kept the old pins: since then each pin warned on every run and
  had no control able to turn it red on its own condition.
- CORE 1.2 says the closed ticket-field list "is owned by `REGISTRY.json`";
  REGISTRY `ticket_states` holds sections, checkboxes and required fields only.
  The list lives in `saipen_engine/board.py` KNOWN_FIELDS. The law names an
  owner that does not hold the fact.

Effect: a permanent WARN wall teaches agents that drift warnings are noise,
which is exactly when a real drift ships.

Repair: re-anchor each pin on the current owner's text with whitespace and
emphasis normalized; retire the three prose-enumeration pins in favour of the
registry-is-owner check; name the real owner document in every message. Keep
the audit_checks.py mutation controls in step so each pin still goes red.

## C2 Publication authority has no single machine owner

- SHIP (phases/ship.md) commits, pushes and tags unless `mode: no-publish`.
  STATE says `mode: full`.
- Sessions cite SRC-039 ("Do not commit/tag/push/release") as a standing
  no-publish policy (E-10908, E-10979). SRC-039 bounds itself: "PAUSED ...
  until this wave is complete"; its wave T-1324 is DONE since E-6179
  (13.09.26). SRC-039 is still ACTIVE.
- SRC-168 (04.10.26) authorized main/release publication after green gates;
  T-1607 then says "no GitHub push without a fresh operator instruction".
- Other sessions commit locally (33 commits ahead of origin); recent ones do
  not (T-1618..T-1626 shipped with no commit: ~15.6k changed lines unstaged).
- The validator FAILs "runtime manifest names a file git does not track"
  (tools/test_t1464_matrix_acceptance.py) and WARNs xpatch-survival and
  release-ledger: it demands commits the cited policy forbids.

- The engine agrees with ship.md that `no-publish` commits nothing
  (release.py `_plan_publishes`); CORE 1.3 says only "no external publish",
  and ship.md attributes the commit ban to CORE 1.3, which does not state it.
- `ticket done` closes own_patch Work under `mode: full` with no release, so
  the finish accepts a SHIP that published nothing while the mode says it must.

Repair: one machine fact for publication (STATE `mode` plus a registry value
for local-commit-without-push if that is the operator's practice); SHIP reads
it; a pausing receipt sets it through a canonical operation and its expiry is
a recorded event, not a citation habit. Operator decision needed on the
policy value; until then: no push, no tag.

## C3 Permanent warnings and their owner tickets

WARNs that no action can clear: log-missing-date (125 sealed pre-date lines),
goal-reauth-untripped (E-1659), hand-authored-op-id (89 exempt history lines).
Each is owned by an eternal BLOCKED ticket (T-1119, T-407) or none. A WARN that
cannot be acted on is history, not a finding; reporting it every run trains
agents to skip the WARN block.

Repair: report sealed-history facts once as a counted history note (not WARN),
keep WARN for actionable states; then the owner tickets have a satisfiable
condition.

## C4 Stated limits nobody enforces

- LOG.md 5564 lines / 1850 KB against "~300 line / ~64 KB soft cap -- seal it
  ... at the next checkpoint". No checkpoint seals.
- BOARD.md 214 KB against "~16 KB soft cap", 164 KB closed-ticket text.

Repair: either the checkpoint/CLEAN path seals and scrubs mechanically when the
cap is crossed, or the cap is restated as what is actually enforced.

## C5 The protocol-markdown "hard cap" is a ratchet

tools/test_protocol_registry.py: 300 KiB -> 301 -> 303 -> 322 -> 324 -> 327 KiB
(T-1595, T-1614, T-1619, T-1624), each time "no rule was dropped". Measured
334663 bytes against 334848 (185 bytes slack). A cap that moves whenever it is
hit is a measurement, not a cap.

Repair: compact the routine-loaded law (duplication across CORE/COMMANDS/OPS,
incident history inside law, which CORE 1.1 already forbids) and hold a fixed
cap with offset-only growth.

## C6 Future gate: stored state contradicts live readiness (T-1638)

`saipen future add` writes a placeholder slice that readiness accepts, so a
fresh gate matures to ELIGIBLE at once; monotone maturation keeps it after the
document adds `needs:`. FG-0046 stores ELIGIBLE while its live reason says
"prerequisite T-1635 is ## TODO". The validator's "BOARD ticket works on future
gate" check is a substring match of the gate id in any live ticket, so the
ticket filing the defect (T-1638) is itself flagged as a duplicate
implementation ticket (validator FAIL).

## C7 Invalid Work rows and stale claims about routes

BLOCKED rows T-1155, T-1172, T-1321 ("--help" parsed as goal text), T-1195
(goal-command tail) say "No canonical route retires a Work row". That is no
longer true: `saipen ticket retire --reason INVALID_INVOCATION` exists
(COMMANDS.md, OPS.md "Retirement transaction"). It needs an operator capsule
that grants the exact rows. The CLI usage line omits `ticket retire`.

## C8 Six permanently red unit tests absorbed into the baseline on a false cause

Six tests in tools/test_legacy_lifecycle_compat.py are red in every family
run; the core-unit baseline absorbed them (b41be4a3) explaining that they read
the live `.saipen/BOARD.md`. MEASURED FALSE: T-113/T-114 are rows of the
test's own AUDAPACK fixture (AUDAPACK_BOARD, line 179), written to a temp root.

Measured cause: `log.bulk_legacy_completion_evidence` (T-150) ends the legacy
generation at the FIRST event that allocates a ticket above the frontier. The
fixture (the AUDAPACK production shape) adds T-190/T-195/T-900 at E-005..E-007
and only then records T-113's `RUN: BUILD` and T-114's `RUN: SHIP` in the
pre-operation grammar (no op id), so real legacy execution evidence falls past
the cutoff and the engine demands an operator attestation for a settled
closure. Two test suites encode opposite boundaries (allocation order vs the
grammar the evidence was written in); the baseline kept the loser silent. The
same shape exists in downstream history (AUDAPACK).

Repair (own ticket): bound the scan by what can only be legacy evidence -- a
RUN line in the pre-operation grammar is legacy whatever its position; a
modern bookkeeping line carries an op id -- keep T-150's protection against
modern bookkeeping, and return the baseline to empty.

## C1 repair evidence (this ticket's slice)

- validate --gate core on this project: cross-doc-drift WARN 12 -> 0
  (findings JSON before/after in the session; categories after: board-soft-cap,
  hand-authored-op-id, goal-reauth-untripped, log-missing-date, log-soft-cap,
  producer-package-stale, subsaipen-uncollected, translation-stale,
  release-ledger, xpatch-survival -- each owned by T-1639..T-1644 or existing Work).
- Red controls: `run_t1637_cases.py <tree>` drives the 12 new audit_checks
  controls with audit_checks' own `validator_output`: 12/12 RED, each anchor
  unique, none present in the unmutated control.
- Downstream (`downstream_diff.py`, scratch copies, originals untouched):
  AUDAPACK 95/95, SAIWORK2 55/55, SAIPENVIEW 4/4, SAITALK 9/9 FAIL lines before/
  after, no new and none gone; cross-doc-drift -3 summary lines each;
  translation-stale +1 is a home-copy artifact (the after-home carries a
  .saipen saitranslate kitchen, the before-home does not).
- Related unit modules (71, every test naming KNOWN_FIELDS, REGISTRY.json,
  COMMANDS.md, audit_checks, ticket_states or validate.py): Ran 1465 OK.
- Budgets: command_resolution 54197/54272; human markdown 334503.
