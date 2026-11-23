# Final Execution Report: Protocol Hardening (SRC-230 / T-1732)

## 1. Executive Summary
- **Ticket**: `T-1732`
- **Source Receipt**: `SRC-230` (`audit/SAIPEN_20261010_1415.md`)
- **Status**: Completed and Verified
- **Subject**: Protocol hardening addressing historical SAI_WEBSITE session observations regarding entry routing, work admission vs queueing, STOP lifecycle safety boundaries, hush/response delivery contracts, and verification linkage.

## 2. Completed Corrective Tasks
1. **New Task Admission & Work Ownership Distinction**:
   - `saipen_engine.entry.start_work`:
     - When an active ticket is already DOING and a new task is received without preemption, `USER_REQUEST_RECORDED` explicitly returns `work_claimed: False`.
     - Added `ownership_boundary` citing the active ticket retaining the execution seat.
     - Preserves active ticket and its `next_action`; user intent is recorded in queue without silent ownership hijacking.
     - When work is genuinely claimed into SCOUT or resumed, returns `work_claimed: True`.
   - `tools/saipen.py`:
     - CLI `start` outputs explicit `execution_instruction` on `USER_REQUEST_RECORDED`, warning the executor not to claim or mutate source for the queued request and directing execution to the active ticket.
2. **STOP Lifecycle Semantics & Safety Boundaries**:
   - `saipen_engine.operations.stop_checkpoint`:
     - Explicitly commits `stop_lifecycle: "STOP_TRANSACTION_COMPLETED"`.
     - Explicitly marks `handback_semantics: "HANDBACK_ONLY"` and `mutation_authorized: False`.
     - Preserves state, phase, task, evidence, and next_action for subsequent clean resumption.
   - `tools/saipen.py`:
     - CLI `stop` returns truthful host enforcement diagnostics: `host_cancellation: "UNAVAILABLE"` and `tool_interception: "ADVISORY_OR_UNAVAILABLE"`.
     - Documents that host tool interception and subprocess cancellation are host-owned (ZAICODE) capabilities; protocol side enforces handback-only semantics.
3. **Routing Order & Protocol Safety Boundaries**:
   - `saipen/BOOT.md` and `saipen/COMMANDS.md`: Existing budget-governed router surfaces left intact. Behavioral safety, execution instructions, and contract reporting enforced deterministically in engine code.
4. **Hush, Response Delivery & Verify Linkage**:
   - Existing authoritative contracts (`EXEC-HUSH-01`, `EXEC-RESPONSE-01`, `VERIFY-ORACLE-01`) verified intact with full behavioral alignment.

## 3. Changed Source Files and Rule Owners
- `tools/saipen_engine/entry.py`: Owned by `CMD-ROUTING-01` / `PROTOCOL-ADMISSION-01`.
- `tools/saipen_engine/operations.py`: Owned by `OPS-EFFECT-01` / `CMD-ROUTING-01`.
- `tools/saipen.py`: CLI dispatch, execution instructions, and host capability diagnostics.
- `tools/test_t1732_protocol_hardening.py`: Dedicated 6-test regression and negative-control suite.

## 4. Exact Validation Outcomes
- Dedicated Suite (`tools/test_t1732_protocol_hardening.py`):
  - `test_user_request_recorded_distinguished_from_claimed_work`: PASS
  - `test_resumed_work_reports_work_claimed_true`: PASS
  - `test_cli_start_instruction_on_user_request_recorded`: PASS
  - `test_stop_checkpoint_contract_and_handback_semantics`: PASS
  - `test_cli_stop_reports_truthful_host_enforcement`: PASS
  - `test_negative_controls`: PASS
  - Outcome: 6/6 PASS (1.91s).
- Neighboring Suites:
  - `test_core_ownership_routing.py`, `test_legacy_lifecycle_compat.py`, `test_t1504_zaicode_adapter.py`, `test_audit_inbox.py`, `test_t1726_closed_contracts.py`:
  - Outcome: 188 ran, 0 failures, 0 errors (24.33s).

## 5. Negative-Control Outcomes
- **Control A (Claim Invariant)**: Invariant check enforces that `USER_REQUEST_RECORDED` cannot report `work_claimed: True`. Detected and passed.
- **Control B (Mutation Authorization Invariant)**: Invariant check enforces that `STOP` cannot report `mutation_authorized: True`. Detected and passed.
- **Control C (Host Boundary Invariant)**: Enforces that `host_cancellation: UNAVAILABLE` cannot claim `mechanical_boundary: True`. Detected and passed.
- **Control D (Ownership Boundary)**: Enforces that active ticket ownership is preserved and not overwritten when a secondary task is started. Detected and passed.

## 6. Confirmed Remaining Limitations
- Subprocess / Host Tool Interception: In ZAICODE, host-side tool execution is launched by the host environment. When a tool call is in-flight or dispatched, mechanical cancellation must be provided by the host runner; protocol cannot kill out-of-process foreign execution without host support.
- This is correctly reported as `ADVISORY_OR_UNAVAILABLE` in the adapter registry and CLI outputs.

## 7. Separate ZAICODE Integration Requirements
- **ZR-01**: Tool-call cancellation: When the host receives a STOP signal or user interrupt, the host process runner should terminate child processes and abort active tool dispatch before passing control back to the agent turn.
- **ZR-02**: Message classification: Distinguish user-authored task ingress from synthetic session injections to ensure automated routing to START only occurs for real user tasks.

## 8. Next Canonical Executable Action
- Advance T-1732 from BUILD to VERIFY, record core-unit family evidence, advance to REVIEW, SHIP, and DONE.
