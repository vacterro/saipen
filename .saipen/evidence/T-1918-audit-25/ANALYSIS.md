# T-1918 — SRC-327 (audit/25.md) Audit Handoff Analysis

**Ticket:** T-1918 [P1]  
**Source Receipt:** SRC-327  
**Layer:** audit/25.md  
**Scope:** Evaluation and claim-by-claim verification of external audit campaign (15 findings across Core, Second Wave, Performance)  
**Date:** 2026-10-25T13:13:00Z  

---

## 1. Executive Summary

Audit layer `audit/25.md` represents external audit campaign `acb-mvnfpgft-f90cec53fc1347fb92f7` generated across three waves against SAIPEN v8.1.0 baseline (archive SHA256 `cde897a4fdb3215d8fc93be555f5977b7cfe8851a80124576de64ad646746b46`).

The layer identifies 15 distinct architectural, safety, and performance findings:
- **Wave 1 (Core):** 5 findings (CORE-001 .. CORE-005)
- **Wave 2 (Second Wave):** 5 findings (W2-001 .. W2-005)
- **Wave 3 (Performance):** 5 findings (PERF-001 .. PERF-005)

Every finding has been independently verified against the live SAIPEN engine source code in `tools/saipen_engine/`. None of the reported code patterns are fabricated; all 15 correspond to verifiable implementation structures in the current tree.

---

## 2. Claim-by-Claim Independent Verification Matrix

### Wave 1: Core Lifecycle & Storage

| Finding | Component & Locators | Defect Description | Live Verification Status |
|---|---|---|---|
| **CORE-001** | `audit_inbox.py`: `scan_layers`, `scan_residue`, `classify` | Unreadable or unresolved audit inbox reports CLEAN. `prove_owned_dir_chain` ValueError and `iterdir` OSError caught and return `[]` with comment "absent or unsafe audit/ is normal empty inbox". | **CONFIRMED** in `audit_inbox.py:132-153`. Unsafe/unreadable audit inboxes must yield typed scan outcomes rather than silent empty sets. |
| **CORE-002** | `audit_inbox.py`: `delete_gate`, `consume_layer` | Absent transport file bypasses Source/Work closure check. `delete_gate()` returns `AUDIT_ALREADY_ABSENT` before calling `intake.status()` or verifying linked Work completion. | **CONFIRMED** in `audit_inbox.py:1360-1368`. Missing file should only permit idempotent cleanup if binding state was previously DELETED. |
| **CORE-003** | `source_append.py`: `append`, `_write_ledger` | Source capture and append registration are separated. An interruption between receipt capture and ledger commit leaves orphan receipts without queued append records. | **CONFIRMED** in `source_append.py:402-451`. Multi-record admission requires recoverable intent or orphan reconciliation. |
| **CORE-004** | `source_append.py`: `derive_normative_clauses`, `_units` | Mixed-format operator handoff drops imperative requirements; long clauses truncated at `MAX_CLAUSE_CHARS` without preserving full source span references. | **CONFIRMED** in `source_append.py:518-580`. Bounded display summaries must not substitute for authoritative requirement spans. |
| **CORE-005** | `source_append.py`: `read_ledger`, `_entry` | Append ledger validation validates root object and list shape, but accepts invalid entry elements (e.g. `[null]`), leading to downstream `AttributeError`. | **CONFIRMED** in `source_append.py:228-243`. Schema validation must validate element dictionaries and field invariants at read boundary. |

### Wave 2: Concurrency, Fencing & Authority

| Finding | Component & Locators | Defect Description | Live Verification Status |
|---|---|---|---|
| **W2-001** | `watchdog.py`: `heartbeat`, `fence`, `mutation_allowed` | Fenced worker regains mutation eligibility. `heartbeat()` does not synchronize with `fence()` mutex; late heartbeat overwrites EXPIRED status. `mutation_allowed()` performs two disjoint loads. | **CONFIRMED** in `watchdog.py:312-406`. Lease transitions require linearizable atomic compare-and-swap semantics. |
| **W2-002** | `host_authority_broker.py`: `acquire_lock`, `release_lock` | Broker singleton lock relies on PID-file liveness without OS handle locking; prone to PID reuse and race conditions during stale lock reclamation. | **CONFIRMED** in `host_authority_broker.py:1282-1310`. Singleton ownership requires OS-backed exclusive handle locks. |
| **W2-003** | `host_authority_transport.py`: `_posix_serve` | Server startup unlinks socket pathname unconditionally before bind without proving existing socket belongs to a dead server; can displace live listener. | **CONFIRMED** in `host_authority_transport.py:465-500`. Endpoint cleanup must verify socket liveness and own-generation binding. |
| **W2-004** | `pending_ingress.py`: `enforce`, `clear` | Ingress obligation is cleared during preliminary check before successful Work admission and provenance witness validation succeed; failed start loses obligation. | **CONFIRMED** in `pending_ingress.py:279-350`. Obligation clearance must commit conditionally at the durable admission boundary. |
| **W2-005** | `operator_task.py`: `admit_host_ingress`, `consume_host_ingress` | Host envelope allocation uses `exists()` check followed by `write_text()`; concurrent deliveries with identical digest prefix overwrite each other. | **CONFIRMED** in `operator_task.py:305-455`. Atomic exclusive creation (`O_CREAT \| O_EXCL`) required for host ingress envelopes. |

### Wave 3: Performance & Scalability

| Finding | Component & Locators | Defect Description | Live Verification Status |
|---|---|---|---|
| **PERF-001** | `source_binding.py`: `advisory`, `_citation` | Closed-work drift projection independently re-reads history and performs $O(D \times E)$ reverse traversals for 348+ DONE tickets. | **CONFIRMED** in `source_binding.py:200-280`. Single-pass reverse index over pre-parsed history reduces complexity to $O(E + D)$. |
| **PERF-002** | `saipen.py`: `_status` | Status command always eagerly builds and serializes 200KB+ `blocker_projection` even when routine machine callers only need computed next action and routing truth. | **CONFIRMED** in `saipen.py:5400-5600`. Compact routing projection mode needed for routine agent polls. |
| **PERF-003** | `test_runner.py`: `run_canonical_suite` | Canonical test suite runner copies entire 378MB project tree into an outer sandbox, then `core_unit.run_family()` copies it again into inner shard sandboxes. | **CONFIRMED** in `test_runner.py` and `core_unit.py`. Reusing authoritative immutable snapshot avoids redundant multi-hundred MB copies. |
| **PERF-004** | `core_unit.py`: `red_sections`, `_run_whole` | Test output is read into unbounded memory; `red_sections()` creates suffix slices for each failure header, yielding quadratic scaling on large failure sets. | **CONFIRMED** in `core_unit.py:80-140`. Streaming test output parser with single-pass sequential section accumulation needed. |
| **PERF-005** | `log.py`: `_DETAIL_CACHE` | Process-global dictionary `_DETAIL_CACHE` retains restored detail text for every compacted event, but no consumer ever reads from it. | **CONFIRMED** in `tools/saipen_engine/log.py:360, 400`. Unused global cache retains multi-hundred KB of text indefinitely without benefit. |

---

## 3. Actionable Clauses and Disposition

The requirements of processing `audit/25.md` under T-1918 are:
1. `SRC-327:R001` [requirement]: Ingest and verify all 15 findings of audit campaign `audit/25.md` against live source.
2. `SRC-327:R002` [requirement]: Formally evaluate Core findings CORE-001..005 and establish verification criteria.
3. `SRC-327:R003` [requirement]: Formally evaluate Second Wave findings W2-001..005 and establish verification criteria.
4. `SRC-327:R004` [requirement]: Formally evaluate Performance findings PERF-001..005 and establish verification criteria.
5. `SRC-327:R005` [requirement]: Confirm existing safety gates remain intact without unauthenticated waivers or speculative shortcuts.
6. `SRC-327:R006` [requirement]: Permit journaled audit inbox consumption of `audit/25.md` upon terminal completion of T-1918.

---

## 4. Verification Evidence

- All findings verified against current codebase via static inspection and symbol tracing.
- Baseline regression test suites pass (`tools/test_audit_inbox.py`, `tools/test_t1875_maintenance_wiring.py`, `tools/test_pending_ingress.py`).
- Analysis artifact documented in `.saipen/evidence/T-1918-audit-25/ANALYSIS.md`.
