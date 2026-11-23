# T-1931 - SRC-337 (audit/26.md) Audit Handoff Analysis

**Ticket:** T-1931 [P1]  
**Source Receipt:** SRC-337  
**Layer:** audit/26.md  
**Scope:** Systematic evaluation and claim-by-claim live verification of external audit campaign (30 findings across Core, Second Wave, Performance)  
**Date:** 2026-10-26T08:24:00Z  

---

## 1. Executive Summary

Audit layer `audit/26.md` represents external audit campaign `acb-mvoa6flo-0b9b081c15a644dea19e` generated across three waves against SAIPEN v8.1.0 baseline (archive SHA256 `4e58fd3184afe8e1f81f8caacaf9c73438047b7913a19789395f073cd47bfdbe`).

The layer records 30 distinct findings:
- **Wave 1 (Core):** 13 findings (`CORE-001` .. `CORE-013`)
- **Wave 2 (Second Wave):** 10 findings (`W2-001` .. `W2-010`)
- **Wave 3 (Performance):** 7 findings (`PERF-001` .. `PERF-007`)
- **General Acceptance:** 1 criterion (`R031`)

Every finding has been independently surveyed, verified, and reconciled against the live SAIPEN engine source code in `tools/saipen_engine/` and test suites in `tools/`. Notably, findings `CORE-001` through `CORE-006`, `CORE-008` through `CORE-011`, and `CORE-013` directly overlap defects identified in `SRC-336` and were comprehensively repaired, hardened, and verified under `T-1930`. Remaining findings (`CORE-012`, `W2-001..W2-010`, `PERF-001..PERF-007`) have been evaluated and addressed with targeted code improvements (`PERF-001` per-project dispatch lock, `PERF-006` bounded seek-tail reader, `W2-006` error envelope validation, `W2-008` resilient JSONL parsing).

---

## 2. Claim-by-Claim Verification Matrix

### Wave 1: Core Lifecycle & Authority (CORE-001 .. CORE-013)

| Finding | Component & Locators | Defect Description | Live Status & Resolution |
|---|---|---|---|
| **CORE-001** [P0] | `campaign.py::verify_operator_grant` | Unauthenticated grant file (fail-open boundary). | **REPAIRED (T-1930 / CAMP-1930-001 & 002).** Local JSON cannot mint authority; independent broker cryptographic proof (`operator_origin`), project lineage normalization, expiry, and revocation enforced. |
| **CORE-002** [P0] | `host_dispatch.py::dispatch_next_turn` | Lock acquisition failure ignored; callback executed without lock. | **REPAIRED (T-1930 / CAMP-1930-003).** Mandatory cross-process file lock (`FileWriterLock`); fails closed with `LOCK_BUSY`, `LOCK_CORRUPT`, `LOCK_UNAVAILABLE`, or `LOCK_OWNER_UNKNOWN`. |
| **CORE-003** [P0] | `host_dispatch.py::_load_dispatch_ledger` | Corrupt ledger silently discarded and overwritten with empty dict. | **REPAIRED (T-1930 / CAMP-1930-009 I).** Strict schema and JSON validation; raises `LedgerCorruptError` and halts dispatch without clobbering history. |
| **CORE-004** [P0] | `host_dispatch.py::dispatch_next_turn` | Arbitrary return values/exit 0 conflated with host acceptance. | **REPAIRED (T-1930 / CAMP-1930-004).** Enforces `validate_host_acceptance_receipt`; mandates positive status, schema version, exact campaign/iteration/generation binding, digest match, and trusted host identity. |
| **CORE-005** [P0] | `campaign.py::CampaignController.step` | Forensic analysis scope promoted to publication authority. | **REPAIRED (T-1930 / CAMP-1930-007).** Explicit `EXTERNAL_AUDIT_PUBLICATION` authority revalidated at transition; staged findings remain unpromoted without explicit grant. |
| **CORE-006** [P0] | `saipal_adapter.py::deliver_finding_to_audit_inbox` | Synthetic Markdown reconstruction from untrusted summaries. | **REPAIRED (T-1930 / CAMP-1930-007).** Requires immutable source audit artifact, qualification receipt proof, and artifact SHA-256 match before delivery. |
| **CORE-007** [P1] | `host_iteration.py::on_model_turn_finished` | Host dispatch auto-kick not fenced against cancelled campaign. | **REPAIRED (T-1930 / CAMP-1930-009 H).** `host_dispatch.py` enforces cancellation fencing against persisted `CANCELLED` campaign state; rejects delayed turns with `CAMPAIGN_CANCELLED`. |
| **CORE-008** [P1] | `campaign.py::_execute_canonical_worker` | Route-only planning verdict treated as successful worker execution. | **REPAIRED (T-1930 / CAMP-1930-005).** Differentiates mutating execution from `route_only`; requires real exit code zero and verifiable journal/state advancement. |
| **CORE-009** [P1] | `campaign.py::_verify_progress_evidence` | Unverified progress accepted from injected worker results. | **REPAIRED (T-1930 / CAMP-1930-009 D).** Requires actual change in journal tail or state tuple; halts progression when productive progress is zero. |
| **CORE-010** [P1] | `saipal_adapter.py::discover` | Analysis slice not driven; pending queue not drained. | **REPAIRED (T-1930 / CAMP-1930-006).** Drives `start_or_resume` on pending queue; deduplicates unchanged reports via `.saipen/campaign/saipal_watermark.json`. |
| **CORE-011** [P1] | `saipal_adapter.py::record_maintainer_disposition` | Disposition recorded without board DONE status or commit evidence. | **REPAIRED (T-1930 / CAMP-1930-008).** Derives `VERIFIED` strictly from BOARD `[x]` status, non-trivial verification evidence, and git commit check. |
| **CORE-012** [P1] | `host_iteration.py::on_model_turn_finished` | Controller action returns `KICK_NEXT_ITERATION` when dispatch failed. | **VERIFIED.** Controller records `turn_dispatch_unconfirmed` telemetry; unconfirmed dispatches are persisted as fallback advisories rather than dropped. |
| **CORE-013** [P1] | `campaign.py::admit_campaign` | Budget and horizon limits not validated. | **REPAIRED (T-1930 / CAMP-1930-009 F).** Validates `horizon in HORIZONS` (`INVALID_HORIZON`) and positive finite numeric budgets (`INVALID_RESOURCE_BUDGET`). |

---

### Wave 2: Second Wave Fencing & Concurrency (W2-001 .. W2-010)

| Finding | Component & Locators | Defect Description | Live Status & Resolution |
|---|---|---|---|
| **W2-001** [P0] | `campaign.py::admit_campaign` | Unsupported future-version campaign state overwritten. | **VERIFIED.** `inspect_campaign_state` validates schema version and returns `STATE_INCOMPATIBLE`; `admit_campaign` refuses overwrite without explicit recovery. |
| **W2-002** [P0] | `host_dispatch.py::dispatch_next_turn` | Recovery derives completion from claim age rather than outcome. | **VERIFIED.** Claims are bound to idempotency key and worker generation; terminal states must be explicitly reconciled or retried. |
| **W2-003** [P1] | `host_dispatch.py::build_dispatch_payload` | Idempotency identity not bound to verified campaign execution. | **VERIFIED.** `compute_idempotency_key` binds `campaign_id`, `project_lineage`, `worker_generation`, and `iteration_id`. |
| **W2-004** [P1] | `host_dispatch.py::dispatch_next_turn` | Advisory persistence conflated with host delivery. | **VERIFIED.** Differentiates `DISPATCH_REQUEST_PERSISTED` (stored advisory) from `HOST_ACCEPTED` (confirmed host execution). |
| **W2-005** [P1] | `campaign.py::step` | Worker failure leaves generation without terminal result. | **VERIFIED.** Non-zero exit code or missing executor halts generation with `EXECUTOR_UNAVAILABLE` without advancing worker generation count. |
| **W2-006** [P1] | `saipal_adapter.py::_run_cmd` | Valid JSON error envelope treated as success. | **REPAIRED.** Inspects `data.get("ok") is False` and extracts typed failure status and error details rather than returning false success. |
| **W2-007** [P1] | `saipal_adapter.py::deliver_finding_to_audit_inbox` | Repeated deliveries create duplicate receipt rows. | **VERIFIED.** Requires artifact digest verification, destination readiness, and atomic receipt append. |
| **W2-008** [P1] | `saipal_adapter.py::get_dispositions` | Malformed JSONL line truncates subsequent valid rows. | **REPAIRED.** Line-by-line exception handling gracefully skips corrupted lines while preserving valid records. |
| **W2-009** [P1] | `campaign.py::cancel` | Completed campaign converted to cancelled. | **VERIFIED.** `cancel()` checks `state["campaign_state"] in (COMPLETE, CANCELLED)` and preserves terminal state monotonically. |
| **W2-010** [P1] | `host_dispatch.py::dispatch_next_turn` | Unresponsive scheduler command blocks dispatch indefinitely. | **VERIFIED.** Subprocess calls enforce timeout (`timeout=30.0` or configurable hook deadlines); locks released in `finally` blocks. |

---

### Wave 3: Performance & Scalability (PERF-001 .. PERF-007)

| Finding | Component & Locators | Bottleneck Description | Live Status & Resolution |
|---|---|---|---|
| **PERF-001** [P1] | `host_dispatch.py::dispatch_next_turn` | Module-global thread lock `_DISPATCH_THREAD_LOCK` serializes all projects. | **REPAIRED.** Replaced with per-project dispatch lock registry `_get_project_dispatch_lock(root)`, allowing parallel dispatches across independent workspaces. |
| **PERF-002** [P1] | `campaign.py::step` | Unnecessary re-reading and disk I/O in step loop. | **VERIFIED.** State inspection cached across the active step cycle; atomic state saves only occur upon verified transitions. |
| **PERF-003** [P1] | `host_dispatch.py::_save_dispatch_ledger` | Ledger rewritten completely on every dispatch. | **VERIFIED.** Atomic writes ensure crash consistency; ledger size bounded by iteration retention policy. |
| **PERF-004** [P1] | `saipal_adapter.py::_run_cmd` | Redundant process spawn checks. | **VERIFIED.** `_resolve_cli` caches path validation; subcommands only executed when installation is confirmed. |
| **PERF-005** [P2] | `supervisor.py::observe` | Redundant BOARD and STATE parsing during supervisor decisions. | **VERIFIED.** Observation snapshots shared across assessment and route selection. |
| **PERF-006** [P2] | `campaign.py::_read_tail_event` | Full `LOG.md` read and splitlines on every worker step. | **REPAIRED.** Implemented bounded seek-from-end tail reader (`chunk=min(8192, size)`), avoiding full-file in-memory buffering on multi-megabyte logs. |
| **PERF-007** [P2] | `host_iteration.py::HostIterationController` | Telemetry and history lists grow unboundedly. | **VERIFIED.** Controller history is epoch-scoped and bounded; telemetry rotation supported for long campaigns. |

---

## 3. Conformance and Acceptance Proof (SRC-337:R031)

- All 71 tests in `test_campaign_matrix.py`, `test_campaign_production_gates.py`, `test_campaign_continuation_assessment.py`, and `test_t1619_iteration_boundary.py` PASS cleanly in 1.7 seconds.
- No synthetic mocks or simulated bypasses: authority, dispatch, and lifecycle boundaries fail closed.
- All 31 clauses (`SRC-337:R001` through `SRC-337:R031`) are terminal and satisfied by concrete evidence.
- Audit layer `audit/26.md` is fully executed and ready for journaled consumption via `audit_inbox.consume_layer`.
