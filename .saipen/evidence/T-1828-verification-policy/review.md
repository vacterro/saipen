# T-1828 verification policy

User request: Кароч щас уже цирковая ситуация когда на каждый пук уходит по полтора часа тестов - кпд прогресса 2% - нужно решить ситуацию с этим.

Measured baseline: `.saipen/evidence/core-unit/c0780e34235467f5-20261020T134621Z.json`
records 6965 tests, 4943.2 seconds, jobs=1. Existing default CLI sharding already
exists; changing that default would not remove the per-ticket full gate.

The repository explicitly selects focused ticket verification and full publication
verification in `tools/verification_policy.json`. Other projects keep their gate.
The local command is `python tools/core_unit.py focused T-### --pattern test_name.py`;
repeat `--pattern` for direct consumers. It copies one immutable subject, uses the
existing isolated process runner and full unittest stderr parser, rejects zero
tests and any selected red, bounds total test execution to 300 seconds, and
reuses matching successful evidence of unchanged bytes and selection.

Self-review scope: new focused runner and its CLI, core_unit.ship_gate and its
transition caller, release._run_gate, canonical validator's ship branch, phase
instructions and direct gate/closure/publication/lock tests. Review by the executing
agent; no independent reviewer is claimed. Checked the strict policy parse,
current-cycle citation, path confinement and digest, whole-tree freshness,
explicit selection, failed/zero/timed-out runs, cache behavior, process cleanup,
and preservation of the full-family publication boundary. A focused selection
does not claim all tests passed. Review must still judge the chosen scope.

The initial revision's unchanged regression verifier fails on the saved pre-change core_unit
implementation; exact post-change bytes were restored and hash-checked.
Evidence: `prefix-red-final-verifier.log`; pre-change SHA256
82bf7f42282a515d0fc57323698792dbdd695bd6ed2473fcd8d1379cf54a9191.
Verifier SHA256: 051fb0f61e7d929e3ef7b80bf8010e42f1acd9c5a0c76ae892b1f7201bcf0312.

Initial broad affected scope: 146 tests PASS in 118.781 s; an immediate REVIEW
invocation reused the exact-tree record in 1.389 s. Record:
`.saipen/evidence/focused-unit/079e8f042fdb1857-20261020T142449374288Z.json`.
This measures focused scope, not a speedup of executing all 6965 tests.

The real Source consumer then exposed one compatibility defect: focused results
carried `verdict`, while intake.set_disposition requires `status` on an execution
receipt. The final runner supplies both with the same value. Added the direct
capture -> requirement -> executed focused CLI -> IMPLEMENTED integration test.
It fails with EVIDENCE_EXECUTION_FAILED on the old runner and passes unchanged
on the repaired runner. Evidence: `prefix-receipt-compatibility.log` and
`postfix-receipt-compatibility.log`. Final verifier SHA256:
517785ef6d96a6b4e0222f8871fe627b835dda6ad33d8f8cca2e9875861b8602.
Old/new runner SHA256: fd9311071284586c9bff1f69598cff910628cbd8e0cdb53c299d3ecff7e5107f /
957ad5747862cd7aa7f908843d8bf77bca4936d9477483dfd6dc0d37e0f313cf.
Recheck the changed runner and its legacy gate/Source consumers after this
repair; unchanged release, lock and shard code does not require another run.

Final revision: 212 selected tests PASS in 215.484 s. Record:
`.saipen/evidence/focused-unit/7ca3b9b4e7be6717-20261020T143234244847Z.json`.
The review invocation reused the identical record in 1.511 s. Ruff on the new
runner/test and changed release/validator files, plus scoped diff checks, PASS.
The final Core validator reports only the pre-existing EX-000010 dependency
generation failure. This is not claimed green. The full family was deliberately
not rerun for local completion; publication continues to require it.

Canonical finish E-16613 completed T-1828 in pending cohort C-007. Cohort status
reports ready, zero problems, publication pending; SRC-283 is CLOSED with its
single actionable clause VERIFIED. The previously parked T-1821 was unblocked
after this task completed, preserving its recorded review/evidence.

Publication remains owed by a pending cohort. A full-family result must cover
the final content and metadata; targeted evidence cannot publish a batch.
The existing EX-000010 stale installed-generation proof is separate baseline
conformance debt (already present at session entry); it was not waived.
