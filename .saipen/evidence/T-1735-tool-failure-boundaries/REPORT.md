# Forensic & Evaluation Report: Tool Failure Patterns and Protocol Authority Boundaries (SRC-232 / T-1735)

## 1. Executive Summary
- **Ticket**: `T-1735`
- **Source Receipt**: `SRC-232` (`audit/SAIPEN_20261011_1832.md`)
- **Status**: Completed, Verified, and Concluded
- **Disposition**: **NO_CHANGE** for SAIPEN protocol core with explicit authority boundary clarification and verified regression controls.
- **Subject**: Evaluation of repeated deterministic tool-call failure patterns observed in session `sess_719269a7-7b76-475e-beb2-3a30e26011ff` without expanding protocol authority beyond existing evidence.

---

## 2. Verified Contracts and Authority Ownership

### A. Host Domain (ZAICODE)
- **Tool Adapters & Parameter Schemas**: Owned by ZAICODE. Schema enforcement on tool arguments (e.g., `offset` and `limit` requiring integer types, project root path normalization, Read/Write tool bounds) is performed by host runtime adapters.
- **Validation Diagnostics & Feedback**: Returned to model context by the host harness.
- **Subprocess & Host Tool Interception**: Host-level mechanical control.

### B. Protocol Domain (SAIPEN)
- **Lifecycle & Governance**: Owned by SAIPEN (`CORE.md`, `OPERATIONS.md`, `STATE.md`).
- **Response Surface**: Governed by `EXEC-RESPONSE-01` (`saipen/EXECUTION.md`). Standard ordered control fields (`STATUS`, `RESULT`, `BLOCKER`, `OPERATOR ACTION`, `NEXT EXACT ACTION`, `VALIDATION`, `EFFICIENCY`, `DETAILS`) and typed reason budgets (`COMPACT_FINAL`, `SILENT_CONTINUATION`, etc.).
- **Execution Silence**: Governed by `EXEC-HUSH-01` (`saipen/EXECUTION.md`). Discretionary progress narration suppressed; higher host narration takes precedence.
- **Evidence & Verification Gates**: Governed by `VERIFY-ORACLE-01`, `CORE-UNIT-EVIDENCE`, and bounded verification retry caps (`verify_attempts` on tickets).

**Boundary Determination**: Transferring ownership of host-level agent tool invocation errors (such as bad path arguments or string types in integer parameters) into SAIPEN protocol would violate the explicit authority boundary. SAIPEN protocol maintains its declared obligations and does not mutate or claim host-side tool adapters.

---

## 3. Evidence Classification & Findings

| Pattern / Item | Classification | Owning Layer | Determination / Action |
|---|---|---|---|
| 1. Eleven Read failures from invalid root | Execution-agent error | Host / Agent | Normal agent parameter correction; not a protocol defect. |
| 2. Three schema validation failures (string offset/limit) | Schema validation rejection | Host (ZAICODE) | Host tool adapter enforces integer types; agent corrected types. |
| 3. Host response contract metadata (enforcement: none, replyLanguage: null) | Host reporting state | Host interface | SAIPEN response surface is enforced by `response check` / `response style` API. |
| 4. Incomplete export | Forensic limitation | Inspection tooling | Export is partial by design; does not prove historical invalidity. |
| 5. Synthetic `todo_reminder` separation | Provenance boundary | Protocol (`intake.py`) | Synthetic system reminders are correctly isolated and never become human instructions. |

---

## 4. Test Cases Evaluation Matrix (A through J)

- **Case A (Repeated invalid path with no new evidence)**: Unchanged repetitive calls represent execution-agent loops; agent is guided by host diagnostics.
- **Case B (Invalid path followed by verified correction)**: Legitimate retry with corrected arguments; successfully accesses target; autonomy preserved.
- **Case C (Repeated schema failures with unchanged argument types)**: Host schema rejects improper types until parameter types are corrected by agent.
- **Case D (Transient failure followed by successful recovery)**: Normal execution autonomy; transient errors must not be labeled protocol drift.
- **Case E (Legitimate retry after an external state change)**: Valid recovery after mtime or environment state modification.
- **Case F (Repeated errors from different tool targets)**: Distinct diagnostic encounters across different targets, not an equivalent repeated failure loop.
- **Case G (Compact forensic export with omitted messages)**: Missing history from compact exports is not treated as evidence of invalidity.
- **Case H (Synthetic reminder versus genuine user instruction)**: Provenance separation verified: synthetic injections do not mint user task authority.
- **Case I (Protocol version observed after historical execution)**: Live protocol version is 8.1.0; history is sealed in append-only `LOG.md`.
- **Case J (DONE frontmatter with stale narrative)**: Closed ticket narrative in frontmatter does not override the canonical event ledger.

---

## 5. Non-Goals and Stop Conditions Honored
- Did **not** modify ZAICODE-owned runtime components or tool schemas.
- Did **not** introduce a universal retry prohibition (agent autonomy for corrected retries is preserved).
- Did **not** reopen completed Wintage work from stale prose.
- Did **not** infer missing history from compact exports.
- Recorded a bounded **NO_CHANGE** determination for core protocol logic with regression coverage and evidence verification.

---

## 6. Regression & Verification Results
- **Dedicated Suite**: `tools/test_t1735_tool_failure_boundaries.py`
  - Ran 6 tests:
    - `test_authority_boundary_host_vs_protocol`: PASS
    - `test_synthetic_reminder_vs_user_instruction_provenance`: PASS
    - `test_retry_classification_correction_vs_unchanged`: PASS
    - `test_cases_a_through_j_matrix`: PASS
    - `test_negative_controls`: PASS
    - `test_exec_response_and_hush_contracts`: PASS
  - Result: 6/6 PASS (0.013s).
- **Core Unit Test Family**: Verified fresh before ticket review/closure.
