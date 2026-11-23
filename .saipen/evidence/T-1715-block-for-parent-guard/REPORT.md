# T-1715 — `block-for` must be the owned active-parent handoff

## Defect

`ticket_move`'s generic TODO-block path accepted `block-for` on a merely TODO
parent and stored STATE's UNRELATED active phase tuple as that parent's resume
(E-14412/E-14444). A never-built ticket was later resumed in a phase it never
reached; `dependency-reservation-followup.md` (T-1714) records the observation.

## Change (one guard, `tools/saipen_engine/operations.py`)

`block-for` now requires the parent to be the owned, active DOING ticket — the
ticket STATE names (`state.task == ticket_id`) in a ticket-bearing phase.
Anything else (merely TODO, unclaimed, or foreign active) is refused with
`ILLEGAL_TICKET_LIFECYCLE` at PLAN time, so zero canonical bytes are written.
A foreign live claim is already refused upstream by the SELF-ownership gate
(`_active_claim_refusal` → `TICKET_NOT_WORKABLE`, zero writes); the new guard
does not duplicate it.

Ordinary TODO `block` is a different operation and is untouched.

## Verification — executed regression pair (SAME oracle, pre-fix vs post-fix)

Oracle: `tools/test_t1715_block_for_parent_guard.py` (5 controls, unchanged in
both halves). Subject: `tools/saipen_engine/operations.py`.

Executed through `saipen work regression T-1715 --file
.saipen/evidence/T-1715-diagnostics/regression-contract.json`
(contract `{python} -B tools/test_t1715_block_for_parent_guard.py`, format
`unittest`, before-material `.saipen/evidence/T-1715-diagnostics/pre-fix-operations.py`
= HEAD bytes):

| Half | subject | exit | failed |
| --- | --- | --- | --- |
| FAIL | pre-fix `operations.py` | 1 | 2 |
| PASS | post-fix `operations.py` | 0 | 0 |

Pre-fix the unopened TODO parent returned `BLOCKED_FOR` and wrote
LOG+BOARD+STATE (the reproduced defect). Post-fix it is refused with zero
writes.

## Controls held

- RED: unopened TODO parent → `ILLEGAL_TICKET_LIFECYCLE`, BOARD/STATE/LOG
  byte-identical.
- RED: unclaimed parent → refuse, zero writes.
- RED: foreign-claimed parent → `TICKET_NOT_WORKABLE` (upstream), zero writes.
- GREEN: legitimate owned active-parent handoff → `BLOCKED_FOR` with
  `resume_phase` saved.
- GREEN: ordinary legal TODO `block` → `BLOCK`.

## Neighbours

`test_dependency_resume_liveness`, `test_t1429_deferred_due`,
`test_t1473_handback`, `test_t1458_queue_reservation`, `test_continue_chain`,
`test_orchestration_repair`, `test_t1407_structural_log_compaction`,
`test_ticket_retirement` — all green (133 focused tests, plus the 5 oracle
tests).

## Scope notes

No historical rewrite: E-14412/E-14444 are untouched. No A05 scope growth.
Local no-publish closure.
