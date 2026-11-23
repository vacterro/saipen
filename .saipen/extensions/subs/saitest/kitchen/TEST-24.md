# TEST-24: adversary scenarios at 5706afe0d / tree c66baf69 -- the T-2137 closure land probed (post-DONE lifecycle, closure-gate exactness), crew-run idempotence re-measured on the fresh package, stale-package refusal observed live for saitest's own superseded package, registry canary re-measured green

Identity: source_head 5706afe0d814e734b389d5979bde5bff0d149876; tree
git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195;
role_revision sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08.
Read-only toward the main project; writes confined to .saipen/extensions/subs/saitest/.

## Scenarios and verdicts

- S1 crew-run idempotence (family: order and repetition). Second execution of
  `saipen crew record-run saihunt --package HUNT-029` for the package this epoch
  already bound answers `code: ALREADY_BOUND` exit 0; no double receipt.
  Capture: `_test24_scenarios.txt`.
  Verdict: NOT_REPRODUCED (the double-record damage class does not happen for the
  freshly bound package of this epoch).
- S2 stale-package refusal (family: input abuse), observed live for this role's
  own superseded package: `saipen crew record-run saitest --package TEST-23`
  answers `REFUSE [STALE_PACKAGE] -- TEST-23 is not a current saitest package:
  it must be ready or reviewed and carry the live source triple and the current
  role revision` exit 1; no receipt. Capture: `_test24_scenarios.txt`.
  Verdict: REPRODUCED (the staleness gate fires as designed; minimal input: a
  package whose source_head (13f2e7579...) is not the live triple's head
  (5706afe0d...)).
- S3 post-DONE lifecycle laundering (family: state machine).
  `saipen ticket block-for T-2137 T-2140 <reason>` answers
  `REFUSE [ILLEGAL_TICKET_LIFECYCLE] -- block-for accepts DOING or TODO;
  T-2137 is under ## DONE` exit 1; no board write. The no-reason first attempt
  was refused earlier by the validation gate (VALIDATION_FAILED), the retry with
  a reason reaches the lifecycle gate; both attempts refused, neither wrote.
  Capture: `_test24_scenarios.txt`.
  Verdict: NOT_REPRODUCED (phase-history laundering against the freshly DONE
  T-2137 does not happen).
- S4 closure-gate exactness (families: input abuse, boundary). In-process
  search() probe of tools/saipen_engine/operations.py:9185-9203
  `_PREMISE_DISPROOF_RE`. Designed-accept forms (8 incl. the uppercase form
  which matches because the pattern is compiled re.IGNORECASE): all 8 match.
  Adversarial near-misses (unicode confusable a-acute, plural subject,
  split token, no-verb, wrong noun): all 5 fail closed. Capture: `_test24_gate.txt`.
  Verdict: NOT_REPRODUCED (no sneaky non-disproof wording passes the
  finding_invalidated gate; the first probe run misread the uppercase match as
  a leak and was corrected after reading the re.IGNORECASE flag in source --
  corrected capture records the designed classification).
- S5 structured-refusal canary refresh at this tree (families: boundary,
  order). In-process Result.refuse for each of the seven registered codes
  (CORRUPT_GC_STATE, GC_MAINTENANCE_FAILED, GC_STATE_REPAIR_UNVERIFIED,
  GIT_GUARD_FAILED, INVALID_POLICY_KEY, ROWS_UNRECOVERABLE,
  SOURCE_INDEX_UNRECOVERABLE) plus the unknown-code canary: 0 of 7 carry the
  unregistered_code mark, each code answers its own identifier, the canary
  keeps its mark. Capture: `_test24_fixed.txt`.
  Verdict: NOT_REPRODUCED (the registry land measured clean at TEST-23 remains
  clean at the 5706afe0d tree).

All five scenarios ended in exactly one verdict; no fix was made; no
main-project file was written by this role. Scripts live outside the repo
(C:/Users/vac34/AppData/Local/Temp/cuprobe/), captures and this note are
inside the role namespace.
