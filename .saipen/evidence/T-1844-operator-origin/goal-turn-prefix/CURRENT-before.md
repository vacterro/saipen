# T-1844 current execution

Updated 2026-10-21. The thread goal remains `cc all`, active. The canonical
phase is VERIFY, T-1844, last event E-17007 at this checkpoint. This document
supersedes the earlier BUILD continuation summary preserved in
`preview-prefix/CURRENT-before.md`; original evidence and preimages remain intact.

## Current live run: poll, do not restart

The complete declared core-unit family is running on the frozen current source.
The native parent PID is 21856; exec session 91063 is its live observation
handle. Six OS-confirmed shard children started at 11:14:36 UTC. Their exact
roots and the invocation are in CURRENT-RUN.json. The primary snapshot finished
and the writer lock is free. The run's final record and aggregate verdict are
not yet available. Resume with write_stdin(session_id=91063); if this tool
handle is unavailable, inspect the recorded native process, its actual children,
spools, console artifact and final core-unit records before deciding it ended.
An observation timeout is not a terminal result. Preserve the immutable subject
until the family finishes; no test budget was raised.

## Implemented in this continuation

The caller audit found `authority_capture --dry-run` still deduplicating solely
by text and skipping the real capture's fidelity refusal. It could display an
older model Source or another native event as the Source of a fresh approval,
and present a successful preview despite damaged earlier Source bytes.
The preview now uses the same nonbinding event provenance and event-aware
Source lookup as actual capture. It retains mismatch and Source-corruption
refusals without writing project files, consuming delivery or binding the
broker's Source. The exact operations.py preimage is in preview-prefix/.
No unrelated source changes, staging, commits or publication were performed.

## Current and historical verification

- Current source: canonical focused record
  `.saipen/evidence/focused-unit/f8840587a75c2b7d-20261021T111013156229Z.json`
  PASS, 129 tests, six patterns, 172.156 seconds. It covers the new preview
  controls and inherited authority capture, gate decision, live handoff,
  retirement and supersession contracts. No reuse, no record problem.
- Preview regression: native executed record
  `.saipen/evidence/regression/regression-execution-b6b91392d841421c8557d5e0752cd17d.json`,
  events E-17003/E-17004. The SAME four tests produced four assertion failures
  before and zero failures after. It proves exact-event selection, preservation
  of historical model metadata, fidelity/corruption refusal and query purity.
- Original real-carrier oracle: native executed record
  `.saipen/evidence/regression/regression-execution-8430d0bdec11479cbc55c0d4a1d0f655.json`,
  events E-17005/E-17006. Unchanged eight-test oracle SHA256
  `d51851cf7b403b1e07eb6bc1832b523b936f2ddd9b390e2b2de9cf8075369560`:
  pre-fix eight tests, nine assertion failures, no test errors; current eight
  tests, zero failures. The original ten production preimages and absence of
  the new origin kernel are the before subject. One attempt failed to admit
  its receipt with WRITER_BUSY during the live family's snapshot; after the
  OS-confirmed lock released, the canonical operation completed above.
- The current executed-regression evidence_gate returns null under the native
  launcher's SAME Python and PATH. A diagnostic with a different PATH correctly
  reported verifier-environment mismatch; it did not show source drift.
- Ruff passed for the two files changed in this continuation. Native Python
  has no ruff module; the installed `ruff` executable is the working tool.
- Pre-preview source only: the nine-pattern record
  `f94316c11bed5102-20261021T110406870781Z.json` passed 232 tests. This is
  historical evidence for that generation, not a current full-family claim.

## Open gates and preserved scope

The latest actual canonical validation is `core-current.log`, receipt
`receipt-8cd575b90e09`: FAIL, seven problems and 22 warnings. Six new runtime/test
files are not tracked by Git; EX-000016 binds an earlier installed-engine
generation. Neither issue is waived, hidden by staging, or claimed fixed.
Further canonical checkpoints can make that receipt stale; its findings remain
unresolved. Preserve T-1644's actual publication boundary while finishing local
work. Its full stored record says until decided: no push and no tag.

The complete family must finish, reds (if any) need real diagnosis, and required
verification plus semantic self-review/local closure remain due. Native
source/goal/action tests and real broker identity tests are in the whole family;
selected green checks do not prove that entire family.

Native event issue/register/revoke are implemented on the existing separated
broker and exported client API. No real host callback/spawner invocation or
Freebuff UI positive has been witnessed here. Isolated native identity/process
facts remain explicitly simulated. T-1819 retains the entire SRC-278 native
route/handoff, A-Q live acceptance and original FastPrompter T-1479 recovery;
it cannot be closed by the local kernel or these regression pairs. Keep the
original mission and continue other admitted Work when an actual dependency is
parked. `cc all` is not complete.

## Provisional full-family observations (not a terminal verdict)

The six native shards are executing. Their live stderr already shows failures;
`partial-failures.log` preserves the observed test names. Do not report a green
whole family. Initial failures involve Claude transcript detailed-report
positives, chat-style detailed authority, user-request dry-run/idempotency and
cold goal ingress. Assertion traces are not yet all printed; source reads are
triage only. `test_chat_style` still supplies a raw operator-carrier dictionary
without a native proof. Preserve every original positive and negative assertion
when migrating such fixtures; never restore raw-carrier privilege or relabel
an admitted session/transcript as authenticated operator intent.
No source edit has been made during the running full-family snapshot.
