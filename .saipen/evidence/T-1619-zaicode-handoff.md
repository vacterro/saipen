# T-1619 / SRC-179 — ZAICODE native-controller handoff (SHIP gate path B)

Date: 2026-10-05. SAIPEN-side work is complete and proven at the reference
boundary. The native ZAICODE/SAIRoute edit is NOT done and is NOT available
from this checkout. T-1619 stays at SHIP; T-1618 stays parked behind it.

## Why this handoff exists

The ZAICODE repository is not present here: no `.zaicode` in the repo, no
`../zaicode` checkout, git remote is only `vacterro/saipen`. The enforcement
boundary (the code that receives one model/provider result, decides whether
another iteration starts, emits goal-complete UI, and picks SAIRoute
fallback) lives in ZAICODE and cannot be edited from SAIPEN. Claiming DONE
without that edit would be false green.

## What SAIPEN delivers (done, tested)

Public verdict: `saipen iteration --json` (DIAGNOSTIC, read-only, guard-safe:
`--caps-file PATH`, `--cap NAME=VALUE` repeatable, `--executor ID`,
`--all-exhausted`). Schema v1, closed decision vocabulary
`AUTO_KICK / VALID_TERMINAL / OPERATOR_WAIT / EXECUTOR_CAPABILITY_MISMATCH /
RUNTIME_PAUSED`, derived from STATE/BOARD/router/autonomy recall/valve.
Unknown or unreadable fails safe to `RUNTIME_PAUSED`, never complete.

- `tools/saipen_engine/iteration.py` — pure precedence core (unchanged).
- `tools/saipen_engine/iteration_verdict.py` — canonical projection,
  semantic capability normalization (MODEL != EXECUTOR, fail closed),
  `verdict_allows_goal_complete_ui` gate.
- `tools/saipen_engine/host_iteration.py` — reference HOST FLOW controller:
  `admit_candidates`/`admit_one` fresh per switch, epoch-scoped failover
  (reseat only on fingerprint change), emit-once goal-complete UI,
  in-memory telemetry, zero STATE/BOARD writes.
- Tests: 16 pure unit + 11 controller-boundary E2E
  (`tools/test_t1619_iteration_boundary.py`, E2E-01..E2E-10) — 27 green.
- Docs: `saipen/RUNTIME.md` iteration exit names the command; adapter
  registry zaicode entry names the decision owner, stays ADVISORY (truth).

## What ZAICODE must do (native port)

1. After EVERY model turn, query `saipen iteration --json` (pass current
   executor caps as `--caps-file` saved `saipen runtime --json`, or `--cap`
   pairs) instead of inferring completion from final text, stop reason,
   iteration count, or timeboxing prose.
2. Map the verdict via the reference HOST FLOW:
   VALID_TERMINAL → goal-complete UI (once) + terminate; AUTO_KICK → next
   iteration automatically, Work preserved; OPERATOR_WAIT → stop truthfully;
   EXECUTOR_CAPABILITY_MISMATCH → reroute, never a project blocker;
   RUNTIME_PAUSED → preserve Work, report runtime unavailability.
3. Before EVERY executor/tool-profile switch, run pre-handoff admission on
   the CURRENT candidate's advertised tools (no inheritance); reject +
   telemetry + next candidate on mismatch.
4. Gate ALL goal-complete UI ("Eesmärk täidetud", "Goal fulfilled", "Task
   complete") on `verdict_allows_goal_complete_ui` semantics: known schema,
   VALID_TERMINAL, proven terminality. Unknown/versioned-away → pause.
5. Keep failover negatives for one capability/tool-configuration epoch;
   reseat only when the fingerprint changes (never on A→B advance).

## Acceptance proof required from the ZAICODE side

Re-run the two live incidents against the NATIVE controller: (a) T-1618
BUILD fixture + "SCOUT complete" final text → AUTO_KICK, no completion UI,
next iteration starts, no operator input; (b) SAIOPP-shape caps
(read_tabular + system_todo_write) rejected pre-handoff, compatible worker
selected, same T/phase resumed, no blocker. Then update the adapter
registry `iteration_controller.enforcement` from ADVISORY to the real
mechanical owner.

## SAIPEN acceptance status (honest)

SRC-179 items 1, 2, 6, 7, 8: proven SAIPEN-side. Items 3, 4, 5, 9, 10:
require the native ZAICODE edit above — NOT claimed. When the ZAICODE
owner lands it with the incident proof, T-1619 may proceed SHIP → DONE
(path A) and T-1618 resumes at BUILD.
