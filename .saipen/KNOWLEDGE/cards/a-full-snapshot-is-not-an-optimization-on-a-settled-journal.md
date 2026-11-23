<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: tools/saipen_engine/journal.py, tools/saipen_engine/settled_projection.py, tools/saipen_engine/convergence.py, tools/saipen_engine/closed_contracts.py, status hot path, settled receipts 20k+
trigger: a profile shows several semantic_receipts_for_operation_safe calls in one read-only command and a shared semantic_receipt_snapshot looks like a way to decode once
status: active
evidence: T-2108, .saipen/evidence/T-2108-performance-baseline/BASELINE.json
supersedes: none

# A full receipt snapshot is not an optimization over a bounded index

One `status` command spent its receipt time in three targeted lookups; decoding the
whole settled journal once instead measured eight times slower, so the targeted
index is the accelerator and the "decode once" idea is a regression.

Why:
T-2108 measured one `status` command on a live project with 20542 settled receipts.
Three per-operation bounded lookups (`convergence_stage`, `reverify.work`, `scope`) took
**601.2 ms median (n=3)**. One `semantic_receipt_snapshot(root)` over the same tree took
**5020.0 ms median** — about 8.4x slower. The bounded settled projection is the
accelerator; replacing repeated targeted lookups with one whole-history decode is a
regression, not deduplication.

The same command showed 920 `prove_inside` calls on LOG.md/STATE.md and 1012 bounded
intake reads over 513 files. They look like redundant work but are not: the path proofs
are live TOCTOU re-witnesses inside settled-receipt decode (the owner root is deliberately
re-canonicalized per candidate), and the intake reads come from independent projections
that each own their freshness epoch. Collapsing either into a shared cache weakens
substitution-race or freshness detection.

Related: 61 runtime-generation identity calls resolve to exactly 10 DISTINCT roots (one
per installed agent home), with `identity_session` memoizing correctly. Identical-looking
call counts are not proof of repeated work — count the distinct inputs.

Source and installed engine must be reported separately: repo source 8.1.1 agent-status
p50 was 6.69 s while the installed 8.1.0 engine on the same tree was 19.1 s. That gap is
a release/installation condition needing operator authority, not a source patch.
