# T-1803 / SRC-261 — archived Improve reconciliation

Status: BUILD; root cause reproduced, implementation NOT yet written. The
original source contains 33 canonical actionable clauses. FastPrompter's
separate publication mission is queued as SRC-262; do not preempt T-1803.

## Authority and measured inputs

Canonical START admitted this local P2 candidate and claimed T-1803 for
saipen-cli. Codex admission is DEGRADED / permitted true / verified false;
this is no claim of mechanical admission or operator authority. Existing
operator_required / hard_wait and E-16134 remain unchanged.

AUDAPACK is read-only: lineage-79944d6c0334416ebe1001e97de6c1cc, E-3368,
T-311 BLOCKED. `baseline-observation.json` binds protected files and all six
actual findings in the two requested archived cycles. Mutators ran only on
the explicitly labelled disposable copy, whose root is recorded there.
Actual implementation is `tools/improve.py`; the handoff's
`tools/saipen_engine/improve.py` does not exist. The graph excludes tools/;
fresh exact source reads supply evidence.

## Defect and proposed architecture

reconcile_cycle classifies seats but returns ALREADY_TERMINAL even with
STILL_ACTIONABLE and EMPTY_DRAFT seats. Ordinary archived writers correctly
refuse. Amendment correctly requires an existing disposition. Those ordinary
archive/authority boundaries must remain. cycle_liveness reads only the first
seat and advertises archived empty drafts without a finite historical exit.

Proposed successor: `.saipen/improve-reconciliation/<cycle>.jsonl`, outside
the original immutable cycle directory. A versioned header binds lineage,
cycle and exact original manifest/report/SWEEP hashes. Append-only chained
events bind historical finding identities, evidence hashes, explicit seat
retirement and reconciliation outcome. Never rewrite or mark an original
draft complete; never mint current CONFIRMED authority from archived drafts.

Reuse Improve's `_journaled_write`, project_writer_lock and run_mutation;
extend read_preconditions for the original inputs and identity. Give the
successor a target-aware semantic verifier in journal.verify_improve so
apply and interrupted recovery prove the same schema and bindings. Each
append has a compare-and-swap base hash; stale/concurrent plans refuse.

Reuse the existing sweep and retire verbs with explicit retrospective intent;
reconcile inspects terminal cycles before deciding there is no work. Exact
retries are idempotent; contradictory duplicate decisions refuse. Resolved
dispositions need owned evidence; NEEDS_EXTERNAL_EVIDENCE remains blocked and
visible. Any allowed correction is explicit append-only evidence, preserving
its prior event and exact finding identity.

Liveness must inspect every seat, keep existing primary-seat fields for
compatibility, expose unresolved/blocked historical findings honestly, stop
advertising empty or successfully reconciled archives, and never offer an
impossible archived submit/complete route. Use existing lifecycle classes.

## Validation and safety plan

Write RED semantic controls before production changes, using the existing
test_improve_reconcile fixture by borrowed helper attributes (not TestCase
inheritance or nested suite execution). Cover all 18 requested test classes,
plus both actual historical copies. Run focused neighbors, whole-source
contracts, pinned Ruff, native regression evidence, required full core-unit
family, fresh-process restart and canonical conformance. Preserve all
unrelated dirty changes; engine-before/ stores exact preimages.

Review audit_manifest contract v3. Improve bodies are intentionally absent
from portable snapshots. Define a bounded sanitized forensic adjunct or
versioned opt-in policy; do not silently widen v3 or export an entire improve
directory, credentials, transient state or nested checkpoints. AUDAPACK code
and T-311 lifecycle remain untouched.
