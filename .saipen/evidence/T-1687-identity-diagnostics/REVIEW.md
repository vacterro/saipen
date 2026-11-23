# T-1687: named identity refusals and durable failure diagnostics

Reviewed after the actual VERIFY -> REVIEW transition E-13853. The independent
repository oracle rerun is `review-v1.json` and its preserved raw streams.

The owned changes are exactly the two-file preimage comparison in
`candidate.diff` and the new repository oracle
`tools/test_t1687_identity_diagnostics.py`. Foreign source and index entries
are preserved. Pre-ship index: `26a7e18587caf85f68905f2f6d6e77e55a1ff9c1`.

The actual empty ancestry observation returns IDENTITY_UNAVAILABLE and the
broker's CODE_IDENTITY_UNAVAILABLE. The old first fixture demanded
CODE_NOT_AUTHENTICATED. Both selected fixtures now use a closed shared set
of three named negative reasons; all ledger, capability and process-start
refusal assertions remain. The independent unknown-reason control fails
both borrowed fixtures, so a generic negative cannot buy a green check.

The runner already extracts and bounds each real failure section. The durable
record now retains that existing dictionary as `red_sections`; judgment,
baseline, test discovery and content hashing are unchanged. A real miniature
discovery produces one named failure and checks the persisted reason and
AssertionError, rather than injecting synthetic run metadata.

The repository v1 oracle and exact command/configuration are identical in
both subjects: verifier `af445fe5c899ae7c`. Restoring the two subjects gives
three tests / two failures; live and content-identical fixed control both
pass three tests. E-13849/E-13850 bind the pair. The preliminary queued
external-oracle results are not spent as closure evidence.

Before the family, 65 focused and whole-source-contract tests passed, along
with canonical tools/tests Ruff, Git whitespace and core conformance
receipt-af2318d074d9 (zero problems, nine existing warnings).

The live family ended PASS: 5940 tests, zero red and no leaked sandbox.
E-13851 binds `.saipen/evidence/core-unit/2939b7d4d02c6a51-20261008T234231Z.json`
with SHA256 `9f41450293942b688d5753969ab544f5c23195581c5c0c6b12d209127e4a78f3`.
The independent REVIEW rerun passes all three tests under the same verifier
`af445fe5c899ae7c` and exact live subject
`2939b7d4d02c6a517af9afd37d019d50fe6f31d94c6e02c8f24a61ef94108d34`.
No P0/P1 finding has been established in this bounded source review.

Closure is local implementation/evidence only. Publication authority remains
the unresolved T-1644 decision; no commit, tag, push or installed-runtime
refresh is represented as completed. Rollback restores the two exact `pre/`
files and removes only this Work's new test, preserving all inherited bytes
and foreign index entries.

Memory promotion candidate: none. The existing nested-cleanup and
whole-source-contract cards already carry the reusable decision lessons.
