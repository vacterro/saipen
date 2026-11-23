# T-1316 current verification

No new recovery implementation or regression oracle was needed. The original
ProTrail incident, prefix, hostile third-state, crash/restart, public-entry and
idempotence controls remain intact. Earlier requirement dispositions and their
original pre-fix evidence are preserved, rather than represented as new runs.

Current focused recovery: 34 PASS, 0 FAIL, 0 ERROR, 0 SKIPPED. The transcript
and its ten class counts are `VERIFY-focused.stderr` and `transcript-map.json`.
Classifier 3; bookkeeping-crash 1; crash-window test methods 6 (with the native
window matrix); hostile third-state 3; legal prefixes 2; exact incident and
retry 5; public entry points/conformance 8; raising verifier 3; stale markers 2;
terminal settlement 1. These are test-method counts, not inferred crash counts.

The fresh declared six-shard family ran 4,896 tests with 4,839 PASS, 0 FAIL,
0 ERROR and 57 SKIPPED. No skip is counted as PASS. Expected failures and
unexpected successes are zero. Canonical record:
`.saipen/evidence/core-unit/32267b416e4798f7-20261003T201330Z.json`.
Fingerprint: `32267b416e4798f72b933ba871be7358c79cb85c470d747713ad1598a67c4045`.
`family-counts.json` retains the six native summaries and raw-output digests;
`shards/` retains their exact outputs, manifests, discovery specifications and
ownership records. The declared runner/discovery, jobs=6, timeout=5400 and
baseline are unchanged. The canonical runner reports no leaked sandboxes.

The broader transcript includes journal/nested mutation 11, recovery no-op 10,
source receipts 170, source requirement/disposition dry-run parity 10, and
canonical conformance truth 11. Counts include skipped tests where applicable;
the module inventory alone is not a PASS claim. Exact recovery assertions cover
APPLY, recover, conformance debt, exact retry and hostile fault injection.

Canonical `saipen validate` on the existing disposable project factory outside
every Git worktree produced CURRENT_PASS, 0 blocking findings, 13 warnings.
`fixture-validation.json` retains its actual command and durable receipt.
Ruff 0.16.0 over tools/tests and `git diff --check` pass on the unchanged tree.

Instrument history is explicit: the first output-retention wrapper failed at
cleanup on a non-UTF8 byte, after the six native summaries had completed. It
minted no canonical run record; process exit codes were not retained and are
not invented. `interrupted-capture.json` and `interrupted-shards/` preserve that
attempt. All six owned sandboxes were reclaimed. The corrected decoder matches
the canonical runner's UTF8 replacement decoder and retains the raw bytes.
Known-good skip, real FAILED, missing-summary and non-UTF8 controls pass. The
successful canonical family above is a fresh complete rerun after that repair.

SRC-027:R014's former six foreign-module reds are cleared by this current full
family. SRC-026 belongs to T-1304 and is not adjudicated by this Work. Publication
remains separate from local evidence closure in pending cohort C-004.
