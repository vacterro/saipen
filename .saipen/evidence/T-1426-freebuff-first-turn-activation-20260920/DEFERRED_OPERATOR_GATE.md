# T-1426 — deferred operator acceptance gate

Source: SRC-083 (section 1 and section 18) / SRC-082.
Recorded: 2026-09-20 by glm-5.3-max.
Ticket state: T-1426 is `## BLOCKED` with blocker class `BLOCKED_EXTERNAL`.

## Gate contract

- retry_not_before: `2026-09-21 00:00 Europe/Tallinn`
- operator_action: open a NEW FreeBuff Desktop thread on the disposable managed
  project `V:\_TEMP_\t1425-cc-fixture-2mynjxx8` and send exactly `cc`
- pass_signal: `cc GREEN`
  - first-turn semantics already know `cc` = SAIPEN continue
  - immediate bootstrap/continue behavior
  - no "ambiguous", no carbon-copy/compiler/typo speculation, no clarifying
    question, no repository archaeology to discover what `cc` means
  - reads of canonical STATE/BOARD after command recognition are allowed
- fail_signal: `cc FAIL`
  - resume only the remaining first-turn activation defect
  - keep the existing live RED evidence

This gate is operator-owned. No agent consumes FreeBuff quota attempting the
GUI acceptance. Only the operator supplies `cc GREEN` or `cc FAIL`.

## Preserved implementation and deterministic evidence

- E-7617 BUILD: injectors install all registry freebuff instruction surfaces
  (`knowledge.md` + `AGENTS.md`); focused host-bootstrap suite 25 OK, including
  real installed desktop loader execution (red `{}` -> green block) and 2 red
  controls; live host repaired, block refreshed, file created; live assembly
  probe delivers 3151 B block.
- E-7619 / E-7620 REGRESSION-EVIDENCE FAIL/PASS pair over the same oracle:
  pinned pre-fix `inject.ps1` blob -> loader reads nothing; post-fix -> home
  `~/.AGENTS.md` carries the block, test_30 green.
- E-7621 MANUAL-VERIFY STEPS + EXPECTED (the gate above, as a request).
- E-7622 VERIFY rungs green so far; no full-green claim until the operator
  reports the live GUI result; `conf: low` for the pending manual gate.

Root cause proven at E-7614: FreeBuff Desktop loads first-turn knowledge only
from `~/.AGENTS.md` / `~/.claude.md` (bundle `loadUserKnowledgeFiles`,
`KNOWLEDGE_FILE_NAMES=[AGENTS.md, CLAUDE.md]`); `~/.knowledge.md` is invisible
to it; the old injector wrote only `~/.knowledge.md`.

## On operator result

- `cc GREEN`: resume T-1426, capture the live GREEN evidence, run VERIFY to
  completion, perform final REVIEW, close canonically if acceptance holds.
- `cc FAIL`: resume only the remaining first-turn activation defect; do not
  discard the live RED evidence.

## Representation note

The protocol has no native time-aware blockage field or projection
(`retry_not_before` exists only as prose here). The due instant, the operator
action and the pass/fail signals therefore live in the blocker field and in
this evidence file, and the missing due surface is measured separately as
T-1429.
