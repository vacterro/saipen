# T-1841 — restore the pinned full Ruff gate

The exact configured `ruff==0.16.0 check tools/ tests/` gate reported 210
inherited findings in twenty files. The final same command exits zero.
This is a bounded cleanup, not a runtime feature or a verification-policy
change. All original twenty-file bytes and the pre-existing index identity
are preserved under prefix/ and prefix-manifest.json.

Formatting and fifty-nine literal splits were accepted only when the complete
file AST stayed identical. Runtime string/regex values remain identical except
for the removed equivalent duplicate literal pair. The later duplicate
verification_contract mapping entry had the same inline value; ordered mapping
items are proven identical. Four boolean conditions now return their boolean
results directly. Unused local bindings retain their complete RHS evaluations.
Unused imports removed only test-module bindings, never imported TestCases.
The Cyrillic continuation tokens retain identical compiled codepoints.
Existing explicit import-path bootstrap markers remain in place.

All test declarations and assertion counts are unchanged. One receipt assertion
selects index zero from the same fully enumerated list through a named local;
its predicate and expected value remain intact. Module documentation whitespace
is cosmetic. semantic-audit.json records exact source hashes, changed functions,
the single equivalent assertion expression, runtime values and index checks.

An initial narrow-rule RUF100 run removed required existing noqa markers as
well. That attempt was rejected and preserved under narrow-fix-rejected/;
only this attempt's source edits were restored from prefix/. The accepted pass
uses the complete configured rules with only the intended fix classes enabled.
No other user's source or index bytes were reverted.

## Actual validation

* Full configured pinned Ruff: zero findings. Whitespace check passes.
* Current ten-pattern record:
  `../focused-unit/872b291b3570fe30-20261020T225634312686Z.json`.
  It reports 202 tests: 201 execute successfully and one pre-existing actual
  FreeBuff-host acceptance test explicitly skips. Simulated host checks are
  not real host acceptance; the skipped probe grants no LIVE proof.
* The isolated selection reports 206.422 seconds. REVIEW independently reuses
  its exact unchanged generation in 7.219 seconds; no new execution is claimed.
* Canonical current core reports CURRENT_PASS. Real EX-000015 renews the
  unchanged original SAI Accounts contract for this engine generation through
  three actual unskipped broker/project checks. Original receipts and reports
  are preserved; canonical project bytes remain unchanged and the private
  fixture/grant is cleaned up.
* Recorded process ids are pre-close observations, as the existing runner
  documents; cleanup completed. No sandbox was retained.

The source audit is by the executing agent; no independent agent or human
review is claimed. MCP graph/coverage tools were unavailable; exact paths,
source, current ASTs and direct behavior tests were used. No performance
speedup or full campaign/publication acceptance follows from this cleanup.
T-1829 still owns final metadata, all mandatory families/platform/distribution
gates, original Source coverage and the reviewed cumulative publication batch.
