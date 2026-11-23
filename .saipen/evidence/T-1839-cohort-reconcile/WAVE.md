# T-1839 — reviewed cumulative-batch reconciliation

Parent T-1829, SRC-285 R003/R010. The historical BUILD checkpoint waited for
T-1840. Its external-proof dependency is now resolved; final publication still
belongs to the parent campaign and its reviewed complete cumulative batch.

## Change and cause

Earlier pending cohorts bind earlier shared-file generations. Current audit
found 7/6/5/4/1/0 member mismatches in C-007 through C-012; a C-007 ship dry-run
honestly refused STALE_PLAN. Rewriting their historical hashes would erase
review provenance; publishing obsolete generations independently would defeat
the campaign's final-batch verification strategy.

The new `cohort reconcile C-FINAL --from C-OLD[,C-OLD] --review-work T-N`
builds one existing PLAN/APPLY transaction and immutable journal-bound receipt.
An actually finished, currently verified target member covers the complete
inherited/target path union. Original owner, Source, finish, current evidence,
scope and source-byte checks are retained. Old member hashes, BOARD rows and
finish records stay unchanged; source cohorts only acquire a successor edge.
Participating membership freezes through public finish/bind operations too.
Pending links publish nothing; the old Work resolves only through its proven
successor and matching terminal publication evidence. Existing full-generation,
staging, release, remote and authority gates still own publication.

This first route is flat and same-owner. Existing/malformed/nested links,
published/foreign/incomplete/uncovered/stale inputs refuse. It does not invent
a second publisher/controller or claim source completeness across missing
dynamic dependencies. No reconciliation was applied to the real pending
cohorts yet. Immutable proof currently uses the existing local journal; no
fresh-clone portability guarantee is claimed by the new scoped tests.

## Executed evidence and limits

* Actual transaction/CLI, history preservation, Source/owner/current-evidence,
  hash/scope, missing/forged/tampered proof, membership freeze, dry-run/retry,
  stale APPLY, active Work/counter and post-finish citation controls are in
  `tools/test_t1839_cohort_reconciliation.py`.
* Native Ubuntu's most recent complete targeted package reported 19 tests,
  PASS, 61.431 s (`linux-final.log`), before the final empty-edge/strict-schema
  hardening. The final changed forged/empty-edge test passed Windows in
  12.298 s. These are separate scope/generation observations, not a fabricated
  final aggregate. Current complete focused acceptance is still owed.
* `regression-pair.json` replays saved pre-change operations bytes and current
  operations under the same final real-transaction oracle. Before: actual
  missing canonical-reconciliation assertion FAIL. After: PASS. The final
  oracle/context digests match within the pair. This is a controlled module
  replay with adjacent infrastructure held current, not a historical checkout.
* Scoped Ruff 0.16.0 and whitespace passed after the final production changes.
* The canonical validator was measured, not waived: first 34.008 s / 13 FAIL
  findings; after exact index additions, 28.492 s / ONE FAIL finding. Raw
  validator JSON and monotonic wrapper timings are preserved here. These are
  observations of different inputs, not a validator performance comparison.

No measured execution speedup is claimed for this safety repair. Its purpose is
to preserve a truthful single final-batch publication route. Final complete
generation, release, installation/platform and original campaign controls
remain owed. Source fallback was used because graph/coverage MCP is absent.

## Tracking repair and remaining mandatory gate

The 12 new campaign files were added with an exact path list. `index-additions.json`
proves the index delta contains only those additions and every previously
staged byte outside them is preserved. This is tracking preparation, not a
commit/clone/publication claim. No unrelated index cleanup occurred.

The remaining canonical blocker is T-1653's EX-000010 external closure receipt:
its installed engine generation is old. Automatic revalidation honestly refuses
the legacy check because it carries no authenticated argv/runtime identity.
An older generic machine-runtime test cannot certify current SAI Accounts
application/live acceptance. The old receipt and source references are intact.

T-1840 completed that recovery through authenticated immutable proof renewal.
The subsequent one-line engine correction below required real renewal again:
EX-000014 records three executed unskipped readiness checks, original history
preserved. canonical-validation-current.json reports CURRENT_PASS/exit 0.

## Final inspected revision

The executing-agent source audit found one real acceptance defect: successor
publication defaulted a missing release cohort_id to the desired target. A
real canonical-transaction fixture reproduced the false resolution. The
comparison now requires the explicit matching cohort identity. The existing
publication case retains the matching positive and later-development history,
adds missing/foreign negative controls, and restores the matching receipt.
The unchanged final case fails on the saved publication-prefix subject and
passes on the correction. Canonical executed pair:
`../regression/regression-execution-10e0a56919ec41129b2fafc8114dc49b.json`.
The original feature pair was also refreshed with unchanged final feature
oracle/context; prior artifacts remain under prior-oracle/.

The final complete Linux module reports 19 PASS in 67.190 seconds, no skips
(linux-postfix-complete.log). The final four-pattern Windows package reports
105 PASS in 221.375 seconds:
`../focused-unit/08c4c80e3de18442-20261020T223015682093Z.json`.
REVIEW independently reused those exact unchanged bytes in 7.047 seconds.
This is scoped acceptance, not final full-family or publication evidence.
The earlier 105-test record preceded the corrected identity oracle and cannot
certify this final generation. No execution speedup is inferred from their
different wall times.

The exact six-path self-audit and direct callers are recorded in
self-audit-current.json. No independent agent or human review is claimed.
Current implementation-scoped pinned Ruff and whitespace pass; inherited full
Ruff debt is T-1841 and remains before parent final acceptance. No real pending
cohorts have yet been reconciled; their immutable member hashes/finishes and
the final source/full-generation/release gates remain intact.
