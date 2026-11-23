# T-1603 independent REVIEW continuation

The continuation checkpoint is canonical again: `PHASE REVIEW T-1603`.
E-12031 preserves the previous freeform action and its recovery. This document
records the new observations; the earlier review artifacts remain intact.

The fixed external driver is unchanged (SHA256
`3918c1b07d3f0e155fc27df1e679983656ee05a8772f4b0455d9ff6d8d20e46f`).
Its current subject has 230 checks and zero failures. The original subject
has 227 checks and the eight expected behavior failures on the observed
confirmation run. The hostile authority and conflict controls produce three
and one failures respectively. Their records and complete output are here.

The first original-subject run also reported a ninth failure: its finish-gate
fixture stayed in SCOUT when VERIFY was expected. That record is preserved
as `red.json`. The diagnostic confirmation kept the fixed driver's bytes
and subject unchanged and logged refused transitions; it reproduced only the
eight expected failures. `transition-refusals.json` contains the expected
hostile transition refusals. The extra setup failure is unconfirmed; its
cause is not claimed, and its evidence has not been discarded.

The independently executed fresh declared unit family passed 4855 tests,
red 0, new_red 0, with no leaked sandboxes. It was not reused. E-12033 cites
`.saipen/evidence/core-unit/54ad859af386ae71-20261003T135812Z.json` and its
SHA256. The record reports the complete 4855-test discovery, six shards,
and no partition error.

The complete native scenario gate finished with exit 0: all 44 declared groups,
1354 checks, and no executable failure. `full-current/binding.json` binds the
source fingerprint
`54ad859af386ae71ba05cd6bd0368cad8fa11b18c546eee41f958f1b56ccb7a9`.
No selection, timeout, baseline, assertion, or source edit was introduced.
The snapshot and live source remained unchanged. The independently re-derived
output SHA256 is `f62b185252a5864e2d43654f53032325c0d3051fb8d1e9156ee67483886d025d`.

The producer wrapper subsequently exited 1 during cleanup of a read-only Git
object, after the result and complete output were retained. This is a failed
finalization, not a successful wrapper run. Existing P2 T-1604 owns that defect;
the native scenario command's recorded exit remains 0.

T-1604 has independent native scratch evidence in
`.saipen/kitchen/readonly-cleanup/red.json`: the unchanged EvidenceRun fails
three actual Windows read-only cleanup controls and preserves the foreign
file control. The unchanged external oracle passes all four controls against
the separate proposed subject (`green-draft.json`); production is still untouched.

`review_passes: 1` (continuation of the same review, no source repair between
observations). P0/P1 findings: none within the reviewed scenario fixture diff.
P2 finalization failure remains separately owned by T-1604. Memory promotion:
NO, the existing cards already own the reusable lessons.

Verdict: `DEC: SHIP`. Evidence closure will bind the exact reviewed scenario
bytes into a pending local cohort. Release publication remains excluded.
