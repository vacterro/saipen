# T-1862 SCOUT — symbol inventory (as found, not as assumed)

Ticket: T-1862 / SRC-294
Phase: SCOUT -> BUILD
Date: 2026-10-23
Method: read the current checkout; every symbol below was opened and its
behaviour confirmed by executing it. Nothing here is inferred from naming.

## The surface that produced the operator-report confusion

`saipen status --json` is built in `tools/saipen.py:1739` `_status()`. Its
payload starts at `tools/saipen.py:1993`. It carries exactly one lifecycle
verdict (`phase`, `task`, `next_action`, `computed_next_action`,
`computed_reason`), plus independent diagnostics that are NOT aggregated into
any completeness answer:

| dimension | producer as found | present in status? |
|---|---|---|
| execution phase | `STATE.md` -> `state.get("phase")` | yes, `phase` |
| next action | `router.route_next(...)` (`saipen.py:1844`) | yes, `computed_next_action` / `computed_reason` |
| board backlog counts | parsed `board["tickets"]`, sections | **no** (only `top_workable_ticket`) |
| blockers | `board.project_blockers(tickets)` -> `payload["blocker_projection"]` | yes, per-group |
| audit layers | `audit_inbox.status(root)` -> `payload["audit_inbox"]` counts | yes, counts only |
| source coverage | `intake.active_receipts(root)` / `intake.coverage_summary` | **no** |
| continuation authority | `goal_authority.describe(...)` -> `payload["goal_authority"]` | yes |
| readiness | — | **absent: no symbol exists** |

## Why DONE reads as "project finished"

`saipen/phases/done.md` plus `STATE.md` `phase: DONE` are the only completion
vocabulary the status surface publishes. A project whose last ticket shipped
has `task: none` and `phase: DONE`, and the payload then has no field that can
carry "but 162 source clauses are still UNKNOWN". The operator sees the phase
and reasonably reads it as project completion.

Confirmed on the real SAITULS project (read-only, `V:\___VAC\__K\__CODE\__SAITULS`):

```
phase           DONE / REVIEW transitions observed; task none
board sections  DOING 1, TODO 2, DONE 207, BLOCKED 7
audit/*.md      2 layers present
coverage        230 requirements: UNKNOWN 162, IMPLEMENTED 35, VERIFIED 27,
                BLOCKED 3, NOT_APPLICABLE 3
```

The 162 UNKNOWN figure in the operator's report is real and reproduces.

## Reusable building blocks (no new aggregation invented)

* `intake.coverage_summary(root, receipt_id)` ->
  `{requirements, actionable, terminal, dispositions, unresolved[]}`; strict,
  raises `ValueError` on a malformed ledger.
* `intake.active_receipts(root)` -> cheap index+metadata projection, already
  calls `coverage_summary` per receipt (so a readiness reader that reuses it
  inherits the same strictness).
* `intake.recover_orphans(root)` -> `{ok, code, orphans[]}`; read-only,
  measured 314 ms on this project.
* `audit_inbox.status(root)` -> `{pending[], closed_pending_delete[],
  invalid[], residue_count, clean, ...}`; measured 45 ms.
* `board.project_blockers(tickets)` -> grouped blocker projection with
  `blocker_class`, `root_tickets`, `dependent_tickets`.
* `intake.TERMINAL_DISPOSITIONS` / `ALL_DISPOSITIONS` / `ACTIONABLE_CLASSES`
  — the one disposition vocabulary; readiness must reuse it, never redefine.

## Constraints discovered

1. `STATE`/`BOARD`/`LOG` change only through the CLI. A readiness field must be
   COMPUTED at read time, never persisted.
2. `_status` already performs an expensive projection; readiness must not add a
   second full walk of the same inputs.
3. `saipen.py:2008` `top_workable_ticket` is null when nothing is runnable —
   that is not "project complete".
4. A HARD_WAIT valve is orthogonal: `continuation_authority: operator_required`
   and `safety_valve_mode: hard_wait` must survive any readiness computation
   unchanged.
5. Cross-project reads (`_ZAICODE`, `__SAITULS`) are read-only; readiness must
   never write into a project it reports on.
