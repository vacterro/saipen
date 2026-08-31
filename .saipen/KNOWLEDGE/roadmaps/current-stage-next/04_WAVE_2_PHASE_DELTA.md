# 04 — WAVE 2: EXECUTE `audit/2.md` PHASE DELTA COMPRESSION

## Goal

Compress the ~109 KB phase surface without changing the 16-phase state machine.

## First rule

Do not merge phases.

Do not change phase names merely for size.

Do not move shared prose back into CORE.

## Phase structure

Converge documents toward:

- Purpose
- Entry
- Required reads
- Phase-specific procedure
- Exit
- Failure / Blocked
- Rule references

Universal rules should be referenced, not restated.

## Priority order

Start with largest/highest-value phase documents.

Expected high-value targets include:

- SHIP
- TRANSLATE
- MARKHUNT
- CLEAN
- VERIFY
- REVIEW

## Safety-sensitive phases

VERIFY / REVIEW / SHIP require structured behavioral golden tests before deletion of duplicated prose.

Do not trade semantic precision for byte count.

## Narration independence

Make phase semantics independent from user-visible phase announcements.

This prepares real HUSH later.

Do not implement HUSH in this wave.

## Budget target

Aim phase corpus toward ~60–70 KB.

A justified variance is allowed if semantics demand it.

## Closure

Close `audit/2.md` through normal Source Coverage.

As with audit/1:

do not manually delete the file yet.

Record:

`legacy_closed_pending_inbox_cleanup`

with exact hash.

## Completion bar

1. 16 phases preserved.
2. DFA unchanged unless separately proven defect.
3. Phase corpus materially smaller.
4. CORE does not regrow materially.
5. behavioral goldens green.
6. audit/2 source CLOSED.
7. T-1223 DONE.
8. file retained for native inbox migration cleanup.
