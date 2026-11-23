# T-1804 / SRC-263 — Automatic Ticket-Scoped Self-Audit in `REVIEW`

- **Work Ticket**: `T-1804 [P2]`
- **Source Authority**: `SRC-263` (`.saipen/intake/active/SRC-263.md`)
- **Production File Changed**: `saipen/phases/review.md`
  - Preimage SHA-256: `4303bd1a75080cf7c150b29712bc8110f80b25e5a64066dd3c20af7e3ccf0570` (`2249` LF bytes)
  - Updated SHA-256: `5930d03f960e7878c74db151d71569e6b9305cabef285b6cc486ca596dfbd692` (`5325` LF bytes)

---

## 1. Requirement Coverage Matrix (`SRC-263:R001..R008`)

| Requirement | Summary | Verification Evidence |
|---|---|---|
| `SRC-263:R001` | Extend existing `REVIEW` phase (`saipen/phases/review.md`) with a lightweight ticket-scoped self-audit triggered on attributable implementation delta after `VERIFY` and before `SHIP` without adding phases, AutoHunt, queues, or full repo scans | `saipen/phases/review.md` § `Ticket-scoped self-audit` + `verify_self_audit.py` (`test_r001_r002_r003_r005_r006_contract_and_simplicity_invariants`) |
| `SRC-263:R002` | Specify the 10-point delta-driven self-audit scope (1. owned diff; 2. modified functions & direct callers; 3. changed public contracts & consumers; 4. error/failure paths; 5. null/empty/invalid boundaries; 6. resource lifecycle/cleanup/repeated execution; 7. concurrency/state consistency; 8. actual test coverage; 9. fixture/assertion concealment; 10. unrelated user workflows; no unrelated module scan without dependency/failure signal) | `saipen/phases/review.md` lines 35–42 + `verify_self_audit.py` |
| `SRC-263:R003` | Supplement existing `REVIEW` checks without replacing ticket verifier, regression evidence, oracle integrity, Source acceptance, or security/ownership gates; reuse diff/test evidence without rerunning full Core suite for self-audit | `saipen/phases/review.md` lines 54–60 + `verify_self_audit.py` |
| `SRC-263:R004` | Define finding dispositions for no finding, confirmed P0/P1 in-scope return to `BUILD`, confirmed lower-priority out-of-scope follow-up deduplicated across all `BOARD` sections (never counted as fixed), and unconfirmed suspicion | `saipen/phases/review.md` lines 61–80 + `verify_self_audit.py` (`test_regression_a`, `test_regression_b`, `test_regression_f`) |
| `SRC-263:R005` | Enforce bounded execution and simplicity: one pass per revision, reuse `REVIEW` retry budget, skip fictional code scan on verification-only/`inherited_verified`/no-delta, scoped doc check on doc-only, zero new `STATE`/`BOARD` fields, CLI commands, schemas, or agents | `saipen/phases/review.md` lines 43–55, 89–96 + `verify_self_audit.py` (`test_regression_d`, `test_regression_g`, `test_regression_j`) |
| `SRC-263:R006` | Preserve security and authority invariants: no automatic scope expansion, no unauthorized foreign mutation, no weakened acceptance, no completion with broken required behavior, no post-`DONE` mutation, no fabricated reviewer identity | `saipen/phases/review.md` lines 31–33, 67–70 + `verify_self_audit.py` (`test_regression_c`, `test_regression_e`, `test_regression_i`) |
| `SRC-263:R007` | Verify regression scenarios `A` through `J` with executable positive and negative controls | `verify_self_audit.py` (`12/12` tests `OK`) |
| `SRC-263:R008` | Measure incremental `REVIEW` overhead across small Python, medium multi-file, verification-only, and security-sensitive cases and produce the complete `FINAL REPORT` | `benchmark_results.json` + § 2 below |

---

## 2. FINAL REPORT

### STATUS
`DONE`

### IMPLEMENTATION
- Production file changed:
  - `saipen/phases/review.md` (`2249 -> 5325` LF bytes; SHA-256 `5930d03f960e7878c74db151d71569e6b9305cabef285b6cc486ca596dfbd692`)
- Evidence and verification artifacts (`.saipen/`):
  - `.saipen/evidence/T-1804-self-audit/verify_self_audit.py`
  - `.saipen/evidence/T-1804-self-audit/benchmark_results.json`
  - `.saipen/evidence/T-1804-self-audit/REPORT.md`

### SELF-AUDIT
- **When it runs**: Inside existing `PHASE REVIEW`, after the independent ticket `verify:` re-run and `VERIFY-ORACLE-01` oracle-integrity check succeed, and before `PHASE SHIP`.
- **Trigger**: Runs one focused pass per implementation revision when the ticket owns an attributable implementation delta. Verification-only, `inherited_verified`, and no-delta tickets record that no implementation source scan applies; documentation-only changes receive a scoped documentation consistency check.
- **What is checked**:
  1. Exact ticket-owned implementation diff.
  2. Modified functions and direct callers.
  3. Changed public contracts and relevant consumers.
  4. Error handling and failure paths.
  5. Boundary cases (`null`, empty, invalid input).
  6. Resource lifecycle, cleanup, and repeated execution.
  7. Concurrency and state consistency where relevant.
  8. Actual test coverage of implemented behavior.
  9. Changed fixtures or assertions concealing defects.
  10. Concrete effects on unrelated user workflows.

### REGRESSION
All 10 regression scenarios (`A`–`J`) plus contract/budget and performance controls executed and passed (`12/12 OK` in `verify_self_audit.py`):
- **A. Normal code fix (`PASS`)**: Self-audit inspects owned `calc.py` delta, records revision + `finding=none` in `REVIEW` `LOG` evidence, and transitions `REVIEW -> SHIP`.
- **B. Bug introduced in implementation (`PASS`)**: Self-audit boundary probe catches `ZeroDivisionError` on empty list at `batch.py:2`, records `review_passes: 1`, routes canonically `REVIEW -> BUILD`, fixes defect, reverifies in `VERIFY`, re-audits the new revision in `REVIEW`, and enters `SHIP`.
- **C. Green but weakened test (`PASS`)**: Weakened oracle on unfixed subject is rejected with `ORACLE_CHANGED` (`admissible == False`), while fixed subject under unchanged oracle passes (`ADMISSIBLE`).
- **D. No implementation delta (`PASS`)**: No-delta / verification-only ticket returns `SKIPPED_NO_DELTA` with `files_scanned == 0`; documentation-only delta runs `DOC_ONLY_PASS` without scanning code.
- **E. Existing unrelated defect (`PASS`)**: Defect in `unrelated.py` is excluded from `owned.py` delta inspection (`unrelated_scanned == 0`) and remains unmutated.
- **F. Duplicate finding (`PASS`)**: Out-of-scope P2 finding matching `T-3` in `## BLOCKED` links `T-3` without creating a duplicate ticket (`created_ticket == None`, `counted_as_fixed == False`); novel out-of-scope P2 finding creates `T-4` and is not counted as fixed.
- **G. Repeated continuation (`PASS`)**: Continuation on unchanged revision reuses the recorded `rev=<sha>` inspection (`reused == True`, `files_scanned == 0`); mutating `owned.py` changes `rev=<sha>` and forces a fresh pass (`reused == False`, `files_scanned == 1`).
- **H. Converge (`PASS`)**: `saipen/CONVERGE.md` stages `F` (`**F. FORCED HUNT.**`) and `I` (`**I. FINAL FORCED HUNT.**`) and `saipen/phases/hunt.md` remain unchanged.
- **I. Foreign owner (`PASS`)**: Unauthorized foreign actor mutation on split/foreign-owned `T-1` is refused (`TICKET_NOT_WORKABLE` / `OwnershipSplitError`) with zero canonical byte changes.
- **J. Review retry cap (`PASS`)**: `review_passes: 2` validates cleanly and blocks `T-1` into `## BLOCKED` via `operations.ticket_move(..., "block", ...)` when the finding remains broken on pass 2.

### OVERHEAD
Measured across 25 paired iterations per workload in `verify_self_audit.py` (`.saipen/evidence/T-1804-self-audit/benchmark_results.json`):
- **Small Python correction** (`1` file): baseline `0.1286 ms` -> enhanced `0.3504 ms` (`+0.2219 ms`)
- **Medium multi-file change** (`3` files): baseline `0.2284 ms` -> enhanced `0.7891 ms` (`+0.5606 ms`)
- **Verification-only ticket** (`0` impl files): baseline `0.0609 ms` -> enhanced `0.1058 ms` (`+0.0449 ms`, `files_scanned: 0`)
- **Security-sensitive correction** (`1` file): baseline `0.1194 ms` -> enhanced `0.4326 ms` (`+0.3132 ms`)
- **Protocol context load**: `saipen/phases/review.md` increased from `2249` to `5325` LF bytes (`+3076` bytes); `@ordinary_phase` mandatory route load remains `40801 / 40960` bytes (`+0` bytes route max change, `PASS`).
- **Limitation disclosed**: Local deterministic verifier + AST/diff/boundary inspection overhead is sub-millisecond (`+0.04` to `+0.56 ms`); end-to-end agent turn time in live sessions also includes model inference over the ticket's owned diff, which scales with the ticket's diff size rather than repository size. No unmeasured future savings are claimed.

### COMPLEXITY
- New permanent `STATE` fields: `0`
- New permanent `BOARD` fields: `0`
- New lifecycle phases: `0`
- New public CLI commands: `0`
- New persistent evidence schemas: `0`
- Separate execution agents: `0`

### SAFETY
- Existing `REVIEW` verifier re-execution (`do not read VERIFY's claim of it`), `VERIFY-ORACLE-01` oracle integrity, Source acceptance, `## DOING`-through-`SHIP` rule, `review_passes` retry cap, and seat/ownership invariants are preserved intact.
- Verified by `tools/protocol_budget.py`, `tools/test_protocol_registry.py` (`16/16 OK`), `tools/test_t1670_route_budgets.py` (`10/10 OK`), `tools/test_vocabulary_parity.py` (`22/22 OK`), `tools/test_t1304_review_p0_repair.py` (`21/21 OK`), `tools/test_verify_oracle.py` (`25/25 OK`), and `tools/test_t1645_zero_hunt.py` (`6/6 OK`).

### NEXT EXACT ACTION
Advance `T-1804` through `VERIFY -> REVIEW -> SHIP -> DONE`, then run `saipen cc --json`.
