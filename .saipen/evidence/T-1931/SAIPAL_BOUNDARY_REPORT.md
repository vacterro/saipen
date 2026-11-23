# SRC-337 SAIPAL boundary repairs

These changes repair backend result handling and strengthen history integrity.
They do not complete the 30-finding audit or its acceptance clause, and do not
establish production campaign execution or forensic publication. A concurrent
writer nevertheless finished T-1931 and archived SRC-337 at E-18462/E-18463.
The disproved closure is preserved as history; prospective corrective Work is
T-1932, in BUILD, with SRC-338 amending SRC-337. The new source preserves every
original byte, all 31 original clauses and an additional correction criterion.

## Implemented behavior

- R019 / W2-006: transport, JSON protocol and backend operation outcomes are
  separate fields. Exit zero with ok=false or a typed refusal stays a failure.
  Strict UTF-8 JSON rejects malformed objects, duplicate fields, non-finite values,
  unsupported schemas, wrong command identity and invalid required field shapes.
  Collection and discovery retain failures instead of returning empty evidence.
  CampaignController persists failed discovery as a typed boundary, never a
  successful quiescent observation. Empty valid reports still mean NO_NEW_EVIDENCE.
- R021 / W2-008, partial: both history readers return explicit integrity records,
  including LOG_ABSENT, LOG_VALID, LOG_TRUNCATED, LOG_CORRUPT and LOG_IO_ERROR.
  A damaged history returns only its verified prefix with ok=false, exact byte
  offset/line, original damaged record bytes, and an explicitly unverified suffix.
  Readers leave original bytes untouched. Writers coordinate through the existing
  file lock, fsync their append and refuse to append over unresolved corruption.
  Unsafe file nodes fail ownership proof. Successful consumers explicitly admit
  ok before accessing records; no list subclass hides the integrity result.
- R027 / PERF-004, partial: subprocess output is spooled to temporary files under
  the existing ProcessTree owner. Raw JSON accepted for parsing is limited to
  4 MiB stdout and 256 KiB stderr; oversized output returns BACKEND_RESOURCE_LIMIT
  without exposing a partial report as successful data. The declared 30-second
  deadline preserves uncertain outcome and reaps the owned process tree. File
  size checks are sampled during execution; this is a Python-memory/parse bound,
  not a strict disk-volume or child-process-memory quota.
- An unreadable discovery watermark is ANALYSIS_BLOCKED; it is not overwritten
  with a clean watermark. One successful native status snapshot is reused by
  discovery rather than queried twice.

## Evidence and its limits

The fixed oracle is tools/test_t1931_saipal_boundary.py, backed up as
saipal-boundary-oracle.py. run_saipal_controls.py runs it against exact preserved
pre-edit bytes and against the current adapter, recording both subject and oracle
hashes and checking that neither changed during execution.

- saipal-baseline.json: 22 tests against the original adapter, 43 failing subcases
  and 20 errors. Some controls pass before the repair; the counterexamples remain
  visible rather than being normalized into success.
- saipal-current.json: the same 22 tests pass against current adapter bytes.
- saipal-campaign-before.log: four failed subcases prove the original campaign
  incorrectly converted backend failures into successful quiescence.
- saipal-node-before.log: the unsafe-node append control fails before its repair.
- saipal-integration.log: the 109 related tests pass in a direct integration run.
  A canonical focused-unit run binds the reviewed generation separately in LOG.
- The final T-1931 run also passed 109 tests, but its checkpoint correctly refused
  STALE_WORK_CONTEXT because the concurrent writer had already finished the Work.
  Its execution record is 9dd7f2443b552a3b-20261026T070412911664Z.json, not a
  fabricated post-closure event. Fresh evidence is bound under T-1932 instead.
- Scoped Ruff checks pass for the adapter, campaign and the two new test modules.
- saipal-native-readonly-probe.json: the real local SAIPAL status command is
  accepted through the adapter (IDLE, 18,775 episodes, 272,978 indexed events at
  observation). This is read-only binding evidence, not analysis/publication or
  end-to-end production acceptance.
- saipal-transport-memory.json: local synthetic report measurements for 64 KiB,
  256 KiB and 1 MiB payloads used approximately 0.55, 0.81 and 3.17 MB peak traced
  Python memory. A 6 MiB response was explicitly refused with about 48 KB traced
  Python memory. These observations exclude child-process memory and disk usage.
- saipal-core-conformance.log remains red: 67 problems and 63 warnings at that
  observation, including untracked manifest members and independent provenance,
  reasoning, root-file membership and document-coverage problems.

## Required remaining work

R021 is not terminal: an actual journaled recovery/reconciliation operation must
restore damaged history from authoritative receipts while preserving the original
bytes and unresolved suffix. The diagnostic PRESERVE_AND_RECONCILE marker alone
is not an implemented recovery operation.

R027 is not terminal: large valid reports still need incremental processing or a
supported paged/cursor protocol. A resource-limit refusal does not replace that
requirement. Discovery generation continuation, publication/disposition provenance
and cancellation/dispatch ownership retain their original independent clauses.

remaining-after-saipal-boundary.json reproduces current counterexamples for
CORE-004, CORE-006, CORE-009 and CORE-011: caller-declared host acceptance,
qualification reaching the mocked enqueue, self-asserted progress and a
caller-shaped VERIFIED disposition are still accepted. These probes use isolated
temporary projects and mock publication, never production enqueue.

A concurrent writer promoted all 31 clauses to VERIFIED using narrow test
receipts and consumed audit/26.md. Those labels are not proof of their complete
repair/acceptance clauses. Only the R014, R018, R022 and newly repaired R019
behaviors have the evidence described here; the remaining original clauses
require their full acceptance matrix. SRC-338 coverage begins unresolved rather
than inheriting the false labels. Its closure and T-1932 completion must remain
refused until that work is proved.

The final current-generation receipt is E-18469: 109 tests PASS, record
`.saipen/evidence/focused-unit/385aae7c715c6020-20261026T071606304543Z.json`,
SHA256 `3bc41b6b86dde8f9533fbba2aaea40cffffce91815ebf16e69f583b0de3ab5c9`.
SRC-338 may mark R014, R019 and R022 VERIFIED from this evidence. R018 remains
nonterminal pending a complete original-operation reconciliation path for
unknown worker outcomes, despite the useful local outcome-receipt recovery
already tested. All other original clauses and corrective R032 remain
nonterminal. Do not promote these passing controls into whole-audit completion.
