# T-1690: profile writes and nested unittest isolation

Prepared during the frozen core-unit run; this document is review evidence,
not a phase transition or a whole-family verdict.

The owned delta is the nine preimage comparisons in `owned.diff` plus
`tools/test_t1690_profile_isolation.py`. The surrounding uncommitted work is
inherited and is not attributed to this ticket.

## Requirement checks

- Install, uninstall and rollback select `write_directory`, which follows an
  ambient `CLAUDE_CONFIG_DIR` only for the process's own home. Explicit profile
  selection still wins. Observation uses the unchanged `directory` API.
- `World` explicitly passes its fixture profile. Its regression restores the
  old selector while retaining the new fixture, independently testing the
  fixture boundary rather than relying solely on the product repair.
- Host repair compares each observed profile with the selected write profile
  and hands every Claude installer call that exact profile, including the case
  where the ambient carrier is absent.
- `borrow` invokes a single case with its instance fixtures and cleanups and
  refuses class fixtures. `nested_run` holds the outer process-wide module
  cleanup list while the required publication suite runs. The exception and
  nesting controls check cleanup ordering; a child reproduces the original
  bare-suite hazard and separately checks the protected run through module end.
- The oracle exercises disposable operator and fixture homes. The v3 pair is
  preserved but spent: the complete family found its direct repository
  interlock reference. The v4 oracle retains that guard, observes it through
  the owning hermetic helper and pins its actual held root. Red-v4 restores
  the nine inherited subjects and has 18 tests / 17 assertion failures; live
  and content-identical fixed control both have 18 green tests. Their verifier
  is `e5e7999f4b16d8e7`, cited at E-13803 and E-13804.

## Final evidence

The first whole-family run (session 68845) is terminal FAIL, 5937 tests and
one new red at the interlock source-ownership check (E-13798). The revised
focused check has 22 green tests and canonical tools/tests Ruff passes.

The revised live family completed PASS: 5937 ran, zero red, zero leaked
sandboxes. E-13806 binds its record
`.saipen/evidence/core-unit/18d9a106d60ad9e0-20261008T225702Z.json`.
Index-only repair and local Git configuration leave its source fingerprint
unchanged; the new VERIFY cycle reused that exact record at E-13815.

Core conformance independently failed at receipt-0664a85fba13 because the
owned new test was not tracked by Git (E-13805). After the frozen run ended,
only that test was staged. Every foreign index entry matched the saved index
tree `6212e4dd022016be362f9f9c023daa3a990e12f1`. Current core conformance
passes at receipt-343749f9a6fd: zero problems, nine existing warnings.

The default Git whitespace checker returned 882 false positives on CRLF in
byte-preserved memory. A disposable calibration accepts valid CRLF and still
rejects a real trailing space. The local repository setting now enables
`cr-at-eol`; the original local setting is preserved for rollback, and the
canonical `git diff --check` passes without rewriting any memory. The earlier
failed cycle is not reported as passing; the fresh cycle starts at E-13814.

After the actual REVIEW transition E-13818, the independent ticket run
`run_oracle.py . review-v4-final` passed all 18 tests with the same verifier
and unchanged full subject fingerprint. Raw output and JSON are retained.
The restored pre-fix failures exercise both the original unsafe writer and
the lost outer cleanup; disposable profile canaries make the checks safe.
No P0/P1 finding remains in the attributable ten-file delta.

## Memory promotion candidate

A nested `unittest.TestSuite` can drain cleanups belonging to its caller because
the module cleanup list is process-wide. This is a separate reusable trap from
the existing installer-child profile-selection card. Independent evidence now
supports promotion of one card about borrowing tests safely.

## Publication boundary

This is local evidence closure. T-1644 owns the unresolved publication-policy
conflict (full STATE, expired-wave SRC-039, later SRC-168, and the T-1607
fresh-push constraint at E-13181). No commit, tag or push is claimed here.
