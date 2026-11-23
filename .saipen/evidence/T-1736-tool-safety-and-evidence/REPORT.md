# Forensic & Evaluation Report: Tool Safety Patterns and Validation Evidence Handling (SRC-234 / T-1736)

## 1. Executive Summary
- **Ticket**: `T-1736`
- **Source Receipt**: `SRC-234` (`audit/SAIPEN_20261011_1841.md`)
- **Status**: Completed, Verified, and Concluded
- **Disposition**: **NO_PROTOCOL_CHANGE** for SAIPEN protocol core with explicit authority boundary clarification and verified regression controls.
- **Subject**: Evaluation of tool safety rejections (read-before-write, optimistic concurrency stale writes), schema type checking, task completion idempotence, pipeline exit code preservation, and installation identity.

---

## 2. Authority Ownership & Boundary Delineation

### A. Host Domain (ZAICODE)
- **Tool Schemas & Argument Types**: Enforced by ZAICODE tool adapters. Rejections for string-valued `offset` and `limit` arguments are host schema violations; the agent corrects argument types upon host rejection.
- **File Safety Protections (Read-before-Write & Stale-Write Guard)**: Enforced by ZAICODE file mutation tools (Edit/Write). Edits to files not previously read in the session are rejected. Edits against files modified since last read are rejected under optimistic concurrency.
- **Background Task Management**: Owned by ZAICODE task lifecycle. Calling `TaskStop` on an already-terminated process produces an idempotent terminal response ("not running") and is not a protocol failure.

### B. Protocol Domain (SAIPEN)
- **Validation Evidence & Exit Codes**: Governed by `core_unit.py` and `test_runner.py`. Pipelining commands through shell filters (e.g. `validate | tail`) can mask non-zero exit statuses in standard shells lacking pipefail; SAIPEN's native test family runner captures raw exit codes and full unclipped spool output directly.
- **Installation Identity**: Protocol instances are identified by resolved project root paths, tracked fingerprints, and canonical hashes—never by ambiguous version strings alone.
- **Recovery Policy & Non-Invention of Rules**: Protocol contracts (`EXEC-HUSH-01`, `EXEC-RESPONSE-01`, `RECOVERY-01`, `CORE-001`) operate without inventing new rule identifiers. Repeated equivalent failures without parameter/state change are bounded to avoid endless retry loops.

---

## 3. Evaluated Patterns and Determinations

| Observed Pattern / Requirement | Owning Domain | Evaluation & Determination |
|---|---|---|
| 1. Five Read calls failing inputSchema validation | Host (ZAICODE) | Host tool schema requires integer `offset` and `limit`; corrected calls succeed. |
| 2. Four writes failing on unread files | Host (ZAICODE) | Host read-before-write guard enforces prior Read; agent reads target then modifies. |
| 3. One write failing on stale file state | Host (ZAICODE) | Optimistic concurrency guard protects against concurrent clobbers; agent rereads and reconciles. |
| 4. TaskStop on stopped process | Host (ZAICODE) | Harmless terminal response; idempotent state is distinguished from actionable failure. |
| 5. Validation command piped to tail | Protocol (SAIPEN) | Shell pipe masks exit code; SAIPEN test runner preserves exact process exit codes and complete spools. |
| 6. Installation identity guarantees | Protocol (SAIPEN) | Distinct installation paths with identical version labels are disambiguated by resolved path and fingerprint. |
| 7. Rule identifier hygiene | Protocol (SAIPEN) | No new synthetic rule identifiers are invented; existing contracts and authority boundaries are respected. |

---

## 4. Regression Controls & Verification Matrix
The dedicated regression suite `tools/test_t1736_tool_safety_and_evidence.py` verifies all positive and negative controls:
1. `test_schema_invalid_then_corrected`: Positive/negative pair for schema type validation and argument correction.
2. `test_schema_blind_repeats_bounded`: Negative control capping blind repeated schema failures without parameter changes.
3. `test_read_before_edit_contract`: Verifies rejection of edits to unread files, followed by valid read-then-edit.
4. `test_stale_write_reconcile_contract`: Verifies rejection of stale edits, followed by reread and reconciliation under optimistic concurrency.
5. `test_idempotent_task_stop_terminal_state`: Verifies that stopping an already-terminal task is recognized as harmless and idempotent.
6. `test_pipelined_validator_exit_status_preservation`: Demonstrates shell pipeline exit code masking vs exact exit status preservation.
7. `test_installation_identity_beyond_version_string`: Verifies multi-attribute instance identity (path, fingerprint) beyond version label equality.
8. `test_authority_boundary_host_vs_protocol`: Confirms explicit separation of host-level mechanical guards from protocol evidence obligations.

---

## 5. Non-Goals and Stop Conditions
- No modifications made to ZAICODE or FREEBUFF_SAI source.
- No historical evidence rewritten.
- No new rule identifiers invented.
- No DONE project modified without authorized task admission.
- Bounded **NO_PROTOCOL_CHANGE** determination recorded with complete evidence.

---

## 6. Test Results
- Regression Suite: `tools/test_t1736_tool_safety_and_evidence.py`
  - Ran 8 tests: 8/8 PASS (0.073s).
- Neighbor Suite: `tools/test_t1735_tool_failure_boundaries.py`
  - Ran 6 tests: 6/6 PASS (0.018s).
