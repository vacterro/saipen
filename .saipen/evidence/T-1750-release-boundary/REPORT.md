# T-1750 — local release refusal and validator authority

## Change and scope

A managed project's own `tools/validate.py` no longer becomes the protocol
release gate merely by existing. `_gate_command` selects the validator beside
the running engine. That home validates itself; other roots are passed through
the existing `--project-root` binding.

A caught no-publish refusal now settles its operation ABORTED when the shared
`_no_publish_targets_untouched` predicate proves that no effective closure
target landed. It reuses owned paths, safe file hashes, the existing missing
sentinel, no-op classification and the existing three-way classifier.
Landed bytes, unreadable/unknown state and third-state conflicts retain recovery.
The same predicate replaces recovery's reliance on progress markers alone, so
bytes written before a failed marker cannot be misreported as an unstarted release.

Only `tools/saipen_engine/release.py`, the two corrected expectations in
`tools/test_t1746_crew_terminal_outcome.py`, and the new eleven-case
`tools/test_t1750_release_boundary.py` form this owned implementation delta.
`before/`, `ownership.json` and `owned.patch` preserve exact attribution against
the inherited dirty source. No new product command, state, subsystem or dependency.

The two inherited expectations encoded the reported defects: a fake downstream
validator was treated as a source home's authority, and a refused gate required
manual recovery. The revised checks use the actual runtime home's identity and
the automatically ABORTED journal. New native subprocess controls independently
execute the selected runtime validator and prove downstream code is not run.

## Verification

- Final same-frame executed pair:
  `regression-execution-a5707764dda74550be5a9c5fed2d553c`, E-16035/E-16036.
  Verifier `58a9eb16dcfcd1e352ad6f8b14312bf05dc982df76a57dd0dd8acc2184b162df`
  is identical in both halves. Authentic saved preimage: 11 ran, 8 failed,
  exit 1. Current subject: 11 ran, 0 failed/skipped, exit 0.
- Focused neighbors: 45 crew/terminal, 14 Source-scope and 5 closure-operation
  checks passed. Public CLI: 11 passed. Whole-source refusal/command/UTF-8
  contracts: 21 passed. Ruff 0.16.0 over `tools/ tests/` and owned whitespace passed.
- Complete declared family: 6701 discovered and run, zero red/new red/fixed,
  six complete shards with no partition error. Record
  `core-unit/b7945ae5d07ae1b7-20261015T223328Z.json`, E-16032, SHA-256
  `bf3ec2fa38c309ecc2d8539ec96a863482da4d32e81b2b60dac0ebe1d0a09f36`.
  Current content fingerprint was explicitly compared and matches
  `b7945ae5d07ae1b7ad14ad7a74be9804f55d0b4cd608c1c005ab8819694edc12`.
  Existing platform skips remain as recorded. No sandbox remained; the six
  cleanup diagnostic PIDs were independently queried and none was alive.
- Native T-1695 focused RV-000066: 38/0, CURRENT_PASS dependencies in the live
  persistent command frame. Canonical core receipt-9f1537850fec: CURRENT_PASS,
  zero problems and nine inherited warnings. `RUNTIME-CONTEXT.md` explains the
  actual `CODEX_TOOL_CALL_ID` mismatch and the unchanged binding rules.
- Independent REVIEW reran all eleven owned public controls: exit 0, 11/0,
  no skips, `independent-review.txt`. The exact delta and final oracle were
  inspected against the saved preimage; partial-write, marker-lag, foreign-byte,
  crash-before-body and missing-runtime controls remain meaningful.

The initial host-observed family process disappeared before producing a result.
It was confirmed absent before a replacement was launched; the stopped,
unmeasured observation is preserved rather than called PASS or a test failure.
The later durable supervisor/controller completed exit 0 and wrote the native
family receipt. No running test was duplicated.

## Tracking, limitations and continuation

The validator required tracking for this new test and the already finished
T-1753 test. Exact intent-to-add records were added for those two paths only.
`index-intent.json` proves every foreign index entry stayed byte-identical.
This is not publication; the standing T-1644 publication policy remains open.

No P0/P1 finding remains in the bounded owned diff. Memory promotion: NO;
the existing launcher/environment knowledge card already covers the reusable
lesson. Current-frame proof is not claimed portable to a different host tool
environment; the existing T-1756 policy decision is preserved.

REVIEW passed at E-16042. Exact scope was recorded at E-16043; SHIP entered
at E-16044. Canonical `saipen ship` committed local no-publish operation
`release-a1a49cb73de34e6b825889e10173d406`, returning LOCAL_NO_PUBLISH /
NOT_PERFORMED. E-16045 records the policy skip and E-16046 finishes T-1750
DONE. E-16047 restored parent T-1754 at BUILD without inventing a claim;
the next canonical continuation actually claimed it at E-16048.
The parent T-1754 still owns the restored fourteen-clause SRC-243 scope and its
unproved AG3 acceptance. The broader `cc all` objective remains active.

## Discovery limitations

SAIPEN graph generation 2026-09-01T13:16:39Z deliberately excludes `tools/`.
Graph searches and exact coverage checks were followed by current source reads
for material call paths and guards. No exhaustive graph claim is made.
