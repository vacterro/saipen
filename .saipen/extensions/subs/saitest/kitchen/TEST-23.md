# TEST-23: adversary scenarios at 13f2e7579 / tree 28904dfc -- the seven-code registry land probed (structured refusal, canonical bytes canary), crew-run and block-for idempotence re-measured, OUTBOX enum refusal observed live
Identity: source_head 13f2e7579b29a2892a7130796558ecf5e441bba0; tree
git-delta-v1:bdd63a980a507dc5457e35a5d9b718de7d950aa9757e8f097946bbf4426f26f3;
role_revision sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08.
Read-only toward the main project; writes confined to .saipen/extensions/subs/saitest/.

## Scenarios and verdicts

- S1 structured-refusal probe on the T-2136 registry land (families: input abuse, boundary).
  Tried: Refuse for each of the seven newly registered codes (CORRUPT_GC_STATE,
  GC_MAINTENANCE_FAILED, GC_STATE_REPAIR_UNVERIFIED, GIT_GUARD_FAILED, INVALID_POLICY_KEY,
  ROWS_UNRECOVERABLE, SOURCE_INDEX_UNRECOVERABLE) plus the unknown-code canary.
  Observed: 0 of 7 carry the unregistered_code mark; every code answers its own identifier;
  the unknown-code canary keeps its mark. Capture: `_test23_fixed.txt`.
  Verdict: NOT_REPRODUCED (the unregistered-code defect class is absent at the shipped land).
- S2 canonical registry bytes (family: boundary). Observed: REGISTRY.json equals
  json.dumps(json.loads(file), indent=1, ensure_ascii=False) + newline, byte for byte.
  Verdict: NOT_REPRODUCED (no t1465 shape drift).
- S3 crew-run idempotence (family: order and repetition). Second execution of
  `saipen crew record-run saihunt --package HUNT-028` answers `code: ALREADY_BOUND` exit 0;
  no double receipt. Capture: `_test23_scenarios.txt`.
  Verdict: NOT_REPRODUCED (the double-record damage class does not happen).
- S4 lifecycle-laundering refusal (family: state machine). Replay of
  `saipen ticket block-for T-2136 T-2138 ...` after DONE answers
  `REFUSE [ILLEGAL_TICKET_LIFECYCLE] -- block-for accepts DOING or TODO; T-2136 is under ## DONE`
  exit 1; no board write. Capture: `_test23_scenarios.txt`.
  Verdict: NOT_REPRODUCED (phase-history laundering does not happen).
- S5 strict package-enum refusal (family: input abuse), observed live this epoch: with the
  package status token outside the closed enum (`ready-for-core-review`),
  `saipen crew record-run saihunt --package HUNT-028` answered
  `REFUSE [STALE_PACKAGE] -- not a current saihunt package: it must be ready or reviewed and
  carry the live source triple and the current role revision`, and the parser states the exact
  cause `OUTBOX:3 status 'ready-for-core-review' outside closed enum`.
  Verdict: REPRODUCED (the strict closed-enum refusal fires as designed; minimal input: one
  out-of-enum status token on line 3 of a package).

All five scenarios ended in exactly one verdict; no fix was made; no main-project file was
written by this role.
