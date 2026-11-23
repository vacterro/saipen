# SRC-250 section 7 -- acceptance matrix, state on 2026-10-14

Each row names the real workflow, where it was exercised live in this
repository today, the regression coverage that pins it, and what is still
open. "Live" means it happened on this tree through the canonical commands,
not in a fixture. Nothing here is a simulation reported as acceptance.

| # | Workflow | Live today | Regression coverage | Open |
|---|----------|-----------|---------------------|------|
| 1 | Clean authorized continuation | `continue --json` drove T-1771..T-1785 claim to DONE; the protocol home's 20/20 valve cleared on `cc` with no carrier (E-15333) | test_t1776_protocol_home_valve, test_continue_entry, test_t1775_continue_never_admits_a_seat | consumer projects still need an operator carrier at the valve (SRC-251, T-1780) |
| 2 | Cold start after context loss | this session started cold: BOOT, `continue --json`, phase file, resumed T-1771 at REVIEW | test_cold_agent_truth | -- |
| 3 | Interrupted work, then resume | T-1771 resumed at REVIEW after the previous session stopped at the valve; T-1769's reservations resumed it five times (block-for) | test_dependency_resume_liveness, test_t1619_goal_terminality | -- |
| 4 | Recoverable stale evidence | three STALE_REGRESSION_EVIDENCE refusals re-measured canonically (T-1771) | test_t1771_measure_then_finish, test_t1711_regression_execution | environment-only staleness is not self-healed: T-1756 waits on an operator decision; 17 of 46 re-measures this week were not engineering (baseline) |
| 5 | Unauthorized or foreign-owner refusal | the Core sweep in _SAIRELAY was refused for a live foreign claim (T-1783); foreign engine edits were attributed, not reverted (T-1781) | test_t1771 (foreign session), test_t1775 (foreign seat), test_guard_hostile_matrix | whether other projects may edit the engine: T-1644 (operator) |
| 6 | Completion with source reconciliation | SRC-248 dispositioned clause by clause; SRC-249 stayed ACTIVE after T-1776 finished through `continue` and needed a hand `source close` | test_t1666_receipt_close, test_request_clause_closure | T-1778 (built, measured red/green in a copy, not yet shipped) |
| 7 | Windows managed-account execution | not exercised by SAIPEN | -- | SAITULS owns the Account Control Plane; acceptance is that project's own (SRC-250 section 11) |
| 8 | Concurrent access without lost updates | a zcode session edited tools/saipen.py, operations.py and continue_fallback.py at 12:30Z during a family run; the run re-snapshotted, T-1775's patch was verified as before-plus-patch after it | test_concurrency_independence, test_t1648_transient_replace_lock, test_t1479_core_unit_consistent_copy | engine files take no writer lock against other sessions (T-1644 policy) |

Baseline for comparison: `baseline-20261014.json` (measure_baseline.py).
