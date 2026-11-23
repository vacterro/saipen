# T-1917 / SRC-326 — Premature Model-Turn Handback Incident Report & Controller Contract

- Date: 2026-10-25
- Ticket: T-1917
- Source: SRC-326
- Author: saipen-cli

## 1. STATUS
PENDING_HOST_INTEGRATION (SAIPEN core reference controller verified green; native ZAICODE model-turn-finished callback remains uninstalled in host runtime).

## 2. ROOT_CAUSE
Hypotheses H01 + H10 confirmed by runtime evidence:
- The deployed host (ZAICODE) does not install a native `model_turn_finished` execution hook wired to `saipen iteration --json`.
- In `extensions/adapters/registry.json`, ZAICODE's declared enforcement strength is `ADVISORY`, `response_hook: null`, and `iteration_controller.enforcement: "ADVISORY -- no iteration gate is installed on this host"`.
- When an agent finishes a tool call or emits output in BUILD/VERIFY, the model turn concludes. Because the host lacks the outer-iteration auto-kick hook, it treats the end of the model turn as a prompt for the user, prematurely handing control back to the operator instead of auto-kicking the next model turn.

## 3. CURRENT_CONTROLLER_CONTRACT
- The canonical decision authority is `saipen iteration --json` (`saipen_engine.iteration_verdict.project_iteration_verdict`).
- Bounded decision vocabulary: `AUTO_KICK`, `VALID_TERMINAL`, `OPERATOR_WAIT`, `EXECUTOR_CAPABILITY_MISMATCH`, `RUNTIME_PAUSED`.
- `HostIterationController.on_model_turn_finished` maps `AUTO_KICK` -> `kick_next_iteration`.
- Bounded stall detection (R010 / AC-12): Repeated unchanged states/verdicts across iterations are detected by `ProgressTracker` and paused as `REPORT_RUNTIME_PAUSED`, preventing infinite token loops.

## 4. DEPLOYED_HOST_WIRING
- Hook installation surface: `~/.zcode/hooks/saipen-guard.py` handles operator ingress sealing (`operator_origin`), not outer model iteration dispatch.
- Outer model dispatch remains host-managed by the native ZAICODE application process.

## 5. MODEL_FINAL_VERDICT
- Model prose is data, never a canonical driver.
- A model emitting "NEXT EXACT ACTION: saipen continue" or "BUILD complete" does NOT terminate the goal.
- As long as canonical executable Work remains on BOARD/STATE, `saipen iteration --json` evaluates to `decision: AUTO_KICK`.

## 6. AUTO_KICK_DISPATCH
- On `AUTO_KICK`, the host must invoke the next iteration turn through its execution scheduler without waiting for operator input.
- Original goal identity, active ticket, and phase are strictly preserved across turns.

## 7. TEST_RESULTS
- `tools/test_t1917_premature_handback.py`: 12/12 regression controls PASS (AC-01..AC-17).
- `tools/test_t1619_iteration_boundary.py`: 11/11 E2E controller boundary tests PASS.
- Focused unit evidence run: PASS.

## 8. LIVE_ACCEPTANCE
- Reference controller verified end-to-end SAIPEN-side.
- Full live multi-turn dispatch across host restarts requires the native ZAICODE hook implementation per cross-project ownership rules (SRC-326 §13).

## 9. AUTHORITY_BOUNDARIES
- Model output cannot alter canonical state or bypass safety gates.
- `AUTO_KICK` does not override safety valves or explicit `OPERATOR_WAIT` blockers.
- Outer iteration scheduling is separated from inner deterministic command loops.

## 10. REMAINING_HOST_GAPS
- ZAICODE host bundle must implement a native `on_model_turn_finished` listener that queries `saipen iteration --json` and dispatches `kick_next_iteration`.

## 11. NEXT_EXACT_ACTION
- Close T-1917 and SRC-326 upon verified evidence citation.
- Proceed to T-1916 (continuation discipline) and subsequent queued tickets.
