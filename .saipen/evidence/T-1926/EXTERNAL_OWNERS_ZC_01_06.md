# T-1926 — SRC-333 External Owners ZC-01..ZC-06 Forensic Evaluation

**Ticket:** T-1926 [P0]  
**Source Receipt:** SRC-333 (`audit/writing-block.md`)  
**Scope:** ZAICODE host and SAIMAIL external owners (ZC-01 through ZC-06)  
**Date:** 2026-10-25T15:15:00Z  
**Status:** BLOCKED_EXTERNAL  

---

## 1. Overview and Problem Statement

External audit report `audit/writing-block.md` documents 11 session drift findings (DRIFT-001..DRIFT-011) observed during an interactive session operating on SMART VAC MEDIA COMPRESSOR under ZAICODE 0.0.3 and SAIPEN 8.1.0.

The audit splits corrective responsibility into two distinct ownership domains:
- **Executor A: External Owners (ZAICODE Host + SAIMAIL)** — ZC-01 through ZC-06.
- **Executor B: SAIPEN Engineering** — SP-01 through SP-05 (settled and verified in ticket `T-1927`).

---

## 2. External Requirements Breakdown (ZC-01..ZC-06)

| Owner Item | Severity | Finding | Scope & External Action Required |
|---|---|---|---|
| **ZC-01** | P0 | DRIFT-001 | **Secret Containment & Redaction:** Isolate SAIMAIL private key material from project agents; implement pre-model and pre-export redaction; rotate compromised keys after identifying dependent identities. |
| **ZC-02** | P1 | DRIFT-002, DRIFT-003 | **Authenticated Ingress Bridge:** Ensure genuine operator events flow intact from host UI to broker verification without stripping origin proof or substituting model-supplied caches. |
| **ZC-03** | P1/P2 | DRIFT-006, DRIFT-007 | **Shell, Path, and Error Adapter:** Fix Git Bash POSIX-to-Windows path mangling; ensure pipelines preserve nonzero exit codes; preserve exact argument quoting. |
| **ZC-04** | P2 | DRIFT-008 | **Response Admission & Enforcement:** Enforce Estonian/format response contracts at host boundary or report advisory limitations. |
| **ZC-05** | P2 | DRIFT-009 | **Diagnostic Liveness Budget:** Terminate tool exploration upon encountering definitive non-recoverable authority stops (`RECONCILE_REAUTH_REQUIRED`). |
| **ZC-06** | P2 | DRIFT-010 | **Session Observability:** Ensure host observability metrics reflect actual session projection counters and snapshot boundaries. |

---

## 3. Boundary Classification & SAIPEN Invariants

1. **SAIPEN Internal Owners (SP-01..SP-05):** Completed, tested, and verified under `T-1927` (`tools/test_t1927_sp_owners_matrix.py` 5/5 PASS, focused-unit evidence pass).
2. **External Boundary:** ZAICODE host runtime and SAIMAIL transport code exist outside the SAIPEN protocol repository. SAIPEN cannot directly mutate external binary distributions, host GUI electron layers, or external identity key stores.
3. **Continuation Invariant:** SAIPEN authority safety valve held firm (`RECONCILE_REAUTH_REQUIRED` prevented unauthorized mutation). Legitimate external dependencies cannot be forged or settled without external owner delivery.

---

## 4. Next Exact Action

1. Forward ZC-01 and ZC-02 to the ZAICODE host owner and SAIMAIL maintainer.
2. Maintain rotation plan for exposed key material across dependent agents.
3. Resume full end-to-end acceptance testing upon deployment of updated ZAICODE host and SAIMAIL adapter runtime.
