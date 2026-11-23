# T-1792: canonical conformance revalidation inside continuation

Status: implemented; original native regression pair, independent review and
complete final-tree family PASS; local no-publish closure next.

The first native pair attempt stopped with five post-fix integration failures.
Its validator judged the regression home's `.stdout` and `.stderr` as project
strays (sole exact-layout findings in `pair-diagnosis.json`). This is the existing
T-1749 target/home scope defect, not successful Auto-Doctor proof. T-1792 was
parked at VERIFY on that Work (E-15734), preserving the implementation, fixed
oracle and original pre-fix subject. T-1749 finished canonically (E-15757); an
explicit claim resumed T-1792 in place (E-15758). The same original pair now
records pre-fix FAIL E-15759 and post-fix PASS E-15760:
`regression-execution-bfebfde09421466f9d93eb415942c603.json`, identical verifier
`798d9cddd96ee46a3e113cbfcba8c77bccb421df45e6523aceab8650d100cd4b`.

Authority and scope: current SAIPEN Work T-1792, SRC-253 stage 3. The implementation
reuses `_validate`, `conformance_decision`, `_route_once` and the existing bounded
continuation chain. No external project, profile, admission proof or publication
configuration was changed.

The previous route returned `CONFORMANCE_UNHEALTHY` plus `saipen validate` for
`STALE_PASS`, `NOT_RUN` and `VALIDATOR_VERSION_MISMATCH`, requiring another operator
command. The new continuation executes the existing canonical validator once,
then rereads current routing and durable conformance. It resumes only when both
the validator and the current receipt prove success. Absence of a crew gate after
recovery is insufficient proof. Failure, invalid evidence and existing authority
or recovery refusals retain their exact owner and code.

One shared revalidation budget covers the invocation and its deterministic chain.
Read-only capability and dry runs perform no repair; `next` remains observational.
The response contains Doctor stage, before/after status, validator outcome and
the current receipt's project and checkpoint binding. It creates no authority
receipt or new user request. A LOG write after validation would invalidate the
receipt, so operational evidence stays in the response and canonical validator
receipt instead of an extra post-validation checkpoint.

Current verification:

- `python -m unittest tools.test_t1792_auto_doctor tools.test_t1412_conformance_truth`:
  25 tests, PASS, 76.862 seconds. Real disposable Git fixtures use the actual
  canonical validator. Positive cases cover aged STATE hashes, absent evidence,
  old validator evidence and a ticket finish followed by crew continuation.
- Negative cases cover CURRENT_FAIL, STALE_FAIL, invalid receipt, actual canonical
  validation failure, dry run, read-only capability, immediate restaling, spent
  budget, recovery conflict, install mismatch, missing durable proof and an
  unavailable conformance reader.
- The original stale-STATE case checks that product files and canonical
  STATE/BOARD/LOG stay byte-identical; only one immutable receipt and its derived
  indexes are written. The next healthy cc writes no new receipt. A chain case
  records exactly one ticket finish and one validation within the same cc.
- `python -m ruff check tools/ tests/`, pinned Ruff 0.16.0: PASS after the separate
  T-1793 formatting correction. Its observed pre-change gate had exactly two
  inherited T-1787 lint findings. That dependency finished separately before
  the original parent resumed; no lint waiver or unrelated staging was used.
- Three whole-source contracts and the parked-output tests: 23 tests, PASS,
  25.158 seconds.

The first whole family completed with 6,606 tests and nine new red members, all
caused by the command-resolution context budget: 56,204 bytes against the
unchanged 55,296-byte ceiling. Its complete record is
`.saipen/evidence/core-unit/e86aa5bb69345c20-20261014T221559Z.json` (E-15712).

The compact contract was first checked with the unchanged canonical checker in
scratch (`compact-preview-verdict.json`, E-15711), then applied after the live
family settled (parent correction E-15715). It measures 55,281 bytes. No budget,
authority, accepted status, retry limit, implementation or oracle changed.
All six budget profiles, pinned lint and 34 existing budget/registry tests pass
on the compact source (E-15716). That whole family finished 6606/0. After the
T-1749 source correction, the final coherent tree finished 6609/0:
`core-unit/c408b3c8678817c4-20261014T233138Z.json`. Native evidence for T-1792
reused that proven identical fingerprint, E-15761. The original failures remain
recorded and are not treated as success.

Independent REVIEW reran all 14 Auto-Doctor tests: PASS, 20.749 seconds. Pinned
Ruff and whitespace checks PASS. The implementation diff and fixed verifier
were inspected, including the independently justified T-1412 behavior change.
No P0/P1 finding. Memory promotion: NO (implementation and cheap existing
harness knowledge suffice). The local core signal remains CURRENT_FAIL on
unpublished tracking and existing T-1695 reverify; no global green claim.

The new oracle is fixed for both halves of `regression.json`. The existing T-1412
test now requires the task's new automatic NOT_RUN behavior instead of manual
validation; the reason is recorded in E-15699. No old red evidence is combined
with a changed green oracle.

Inherited instrumentation obstruction: an empty untracked root artifact caused
the canonical consumer validator fixture to fail its runtime home's root-file
set. Exact bytes and restoration instructions are preserved in
`inherited-root-artifact/README.md` (E-15698). T-1749 retains ownership of the
underlying consumer/home validation bug.

This is source and CLI integration evidence. SRC-253's authenticated real host,
ZAICODE integration, simultaneous-cc dispatch proof, restart recovery and broader
recovery classification requirements remain the responsibility of parent T-1791
and later stages. These results do not close the entire Source or prove those
external acceptance conditions.
