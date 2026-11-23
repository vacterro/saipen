# T-1718 acceptance review and bounded repair

This delegation changed only `saipen/phases/verify.md`,
`tools/saipen_engine/acceptance_contract.py` and
`tools/test_t1718_acceptance_contract.py`. Canonical STATE/BOARD/LOG,
Git staging, publication and consumer trees were not mutated.

## Full-family causes

The current acceptance capsule already used `build_boundary`, avoiding the
existing whole-source capped LOG builder detector's `build_event` substring.
Its focused detector passes; no detector or capsule schema was weakened.

VERIFY prose was compressed without changing its requirements. The saved
document has 9995 normalized UTF-8 bytes; the final document has 8787, a reduction
of 1208. `ordinary_phase` is now 40635 / 40960. All six route/document budgets
pass with their original limits. Mandatory/advisory classification, cheapest
first execution, manual result anchoring, unchanged pre-fix oracle controls,
known-good controls, pinned versions, verifier-change invalidation, retry caps
and exit accounting remain explicit. Other phase/documents were not edited.

## Reproduced P1 and correction

The original `_amendment` checked replacement evidence by criterion id alone.
A UNIT PASS for outcome A could therefore be spent on an exactly approved
amendment redefining the same id to outcome B, with no check of B. Both native
amendment and REVIEW admitted that disposable counterexample.

`_declared_at_event` now derives the criterion text belonging to each evidence
event from the immutable native `ticket_verify` contract chronology. Changed or
previously undeclared outcomes require the existing operator observation capsule
bound to the proposed full digest and latest BUILD, including a UNIT witness.
Existing same-text UNIT evidence stays usable; LIVE/MANUAL always retain their
authenticated Source requirement. Exact unchanged criterion/witness amendments
can retain old observations when only implementation notes differ. No witness
floor, approval binding or Source authentication was relaxed.

The negative control is in `NativeEscapeRegressionTests`, already selected by
the canonical execution contract. Three additional positives cover authenticated
UNIT redefinition and unchanged UNIT/LIVE acceptance amendments.

## Evidence

- Exact immediate source/test/prose preimages: `repair-before/`.
- Frozen oracle SHA256:
  `7df4959c2cb2e92c9dedeec34b7e5deb311e09d5e86d4ca8a9a887405b0aaf19`.
- `acceptance-unit-boundary-red-final.json`: the frozen native negative against
  saved acceptance bytes fails one assertion; amendment wrongly returned success.
- `acceptance-unit-boundary-green-final.json`: the identical frozen negative
  passes against the corrected subject. Replay changes only the loaded exact
  acceptance module; actual native operations use disposable projects.
- `acceptance-unit-boundary-final-focused.json`: 95 tests PASS, no skips/failures;
  complete 38-test acceptance module plus acceptance/regression/supersession neighbors.
- `acceptance-unit-boundary-final-structural.json`: 17 tests PASS, including the
  capped LOG producer detector and route/document/line-ending budget controls.
- `acceptance-unit-boundary-final-lint.json`: Ruff 0.16.0 PASS.
- Owned `git diff --check`: PASS.

Final focused/lint/structural source fingerprint:
`cf59cbdd85ceb3051bb053cf2c77eaad0f3e987f6d0500adb3bb33ea54b6c741`.
The final diagnostic-only wording adjustment followed the one-case replay;
the final 95-case invocation includes that unchanged negative on final bytes.

## Remaining admission work

Root must remeasure the canonical unchanged executed regression pair at the
current VERIFY boundary, then run the complete declared family at the final
generation with a functioning OpenCode environment. The prior 6241/17-red
family record remains preserved and cannot justify closure. Final native core,
independent REVIEW and local no-publish finish remain due. Parent T-1717 retains
SRC-216 coverage, the consumer audit and the unresolved missing E-3286 incident;
these changes do not prove Wintage's original live product acceptance.
