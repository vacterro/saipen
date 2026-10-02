# SRC-127 / audit/19.md per-finding triage (T-1543)

Executed 2026-10-02 against the live tree. The audit ran around 2026-09-21
against a 951-event project; the tree is now VERSION 8.0.2, and the state,
recovery and reconcile machinery has been reworked several times since.

All three findings describe ONE fixture shape: a block-parked checkpoint where
`STATE.task` names a ticket, `BOARD.## DOING` is empty and the phase is
`VERIFY`, so the reader refuses to read a defect that only the repair could
explain.

| Finding | Verdict | Decisive evidence |
|---|---|---|
| F1 [P0] PROTOCOL_DEADLOCK — no canonical verb can repair the state | ALREADY_FIXED | `operations.py:243` `REPAIR_OBSERVABLE = ("state", "log", "history_binding")` and `:286` `allow_unbound_history` let the repair read the very damage the validator reports instead of refusing on it; `reconcile.py:2353` and `:3204` read through it. Fixed by commit `180d76a6` (T-1382, closed 18.09.26). Reproduced end to end on a faithful fixture: `saipen recover --json` returns `RECONCILE_REAUTH_REQUIRED` naming `saipen recover --apply-approved-repair <digest>`; running it returns `code: REPAIRED`, STATE lands at `phase: VERIFY / transition_from: BUILD / next_action: "PHASE VERIFY T-1"`, `saipen status --json` and `saipen validate --json` go clean, and a second `recover` returns `CLEAN`. `saipen ticket unblock` and `transition SHIP` still refuse `state-history-binding` — correctly, they are not repair verbs. Pinned by `tools/test_recovery_reachability.py::UnboundHistoryDeadlockTests` (5 passed). |
| F2 [P0] START emits a self-referential resume command | ALREADY_FIXED | The self-referential `resume_command` string is still emitted (`entry.py:626`, `:273`), but it is no longer a fixed point: `entry.py:370` supplies the reconciliation decision and `:618`/`:631` route it into `canonical_next_command`, so the refusal names the move instead of restating itself. Reproduced in order: `saipen start --receipt SRC-001` refuses `WAIT_OPERATOR` and names `saipen recover --apply-approved-repair <digest>`; running that repair; then the SAME `saipen start --receipt SRC-001` returns `code: STARTED`, `ticket: T-3`, `phase: SCOUT`. The receipt IS projectable, which is what the finding said could never happen. Pinned by `tools/test_recovery_reachability.py:1341-1360`. The fixed-point class was closed by T-1397; T-1377 named it. |
| F3 [P1] the guard closes the manual exit | ALREADY_FIXED | Both refusals stay armed and both now carry an executable route, attached at the single result builder so no call site can miss it: `admission.py:1094-1099` sets `canonical_next_command = CANONICAL_NAMESPACE_ROUTE` (`admission.py:724`, `saipen next --json`) on every `PROTECTED_CANONICAL_NAMESPACE`; `admission.py:852-857` routes `NO_ACTIVE_WORK` to `ENTRY_COMMAND`. Evaluated live on the same fixture: writing `.saipen/STATE.md` and deleting `.saipen/BOARD.md` both refuse with route `saipen next --json`; writing `src/app.py` refuses `NO_ACTIVE_WORK` with route `saipen start '<the task, one line>'`; and `saipen next --json` on that fixture returns `action: "saipen recover"`, which names the repair. Pinned by `tools/test_canonical_write_route.py` (13 passed), `tools/test_refusal_routes.py:228-237`, `tools/test_canonical_command_reachability.py` (11 passed). |

## One shared root cause

`operations.py:275-277` states the invariant these three violated: *a defect the
reader refuses to read is a defect no repair can ever reach, because the repair
lives behind the read.* F1 is that invariant broken outright. F2 and F3 are its
two surfaces — both re-printed the caller's own command because the only real
move was unreachable, which is exactly what T-1377 named ("a refusal that does
not change what the model does next is a loop"). T-1382 carries the root cause
in its title and closed it.

## Residual, recorded as unproven rather than dispositioned

On a narrower class the audit's own recipe under-specifies — a LOG with no
`transition to <PHASE>` event, or a `## DONE` row missing `owner` and
`claim_time` — `recover` still returns `RECOVERY_BLOCKED` with
`canonical_next_command: null`, and the `start` refusal still self-references
its `resume_command`. Those are the conservative unprovable-refusals in
`reconcile.py:1854` and the T-1572 class, not the state the audit observed. No
canonical verb was established as reaching them, and none is claimed to. This
is left explicitly unproven rather than quietly folded into a green verdict.
