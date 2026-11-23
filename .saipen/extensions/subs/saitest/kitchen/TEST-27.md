# TEST-27: adversary scenarios at 7ee2ab0dd / tree c66baf69 -- fresh-epoch record idempotence re-measured, superseded-triple staleness refusal observed live, post-DONE lifecycle refused, the T-2062 oracle green on the committed tree, registry canary green

Identity: source_head 7ee2ab0ddb10b19254ff425224ecdf73a91d0df3; tree git-delta-v1:c66baf69a8306f3b95dfc7badb5f72b088f8de8408e933efadc4d149721a1195; role_revision sha256:801fbfdc4be680d87b18cd21e6246d83fad5b474ebd7fe82efa83918cecf2f08. Read-only toward the main project; writes confined to the saitest namespace.

## Verdicts

- S1 (order and repetition): second `crew record-run saihunt --package HUNT-032` answers ALREADY_BOUND exit 0, no double receipt. Verdict: NOT_REPRODUCED (idempotent at the fresh epoch).
- S2 (input abuse): `crew record-run saihunt --package HUNT-031` answers STALE_PACKAGE with the package-triple reason (the superseded 3373fe9f4 triple). Verdict: REPRODUCED (the staleness gate fires as designed; minimal input: a package whose source triple is one epoch behind).
- S3 (state machine): `ticket block-for T-2153 T-2117 <reason>` answers the lifecycle refusal (T-2153 is under ## DONE). Verdict: NOT_REPRODUCED (post-DONE laundering does not happen).
- S4 (regression land): `python -B -m unittest tools.test_t2062_gc_serial` on the committed tree answers OK (verdict read from the combined stream, 3.8s). Verdict: NOT_REPRODUCED (the serialized-GC guarantee holds at the published identity).
- S5 (structured refusal): 0 of 7 registered codes carry the unregistered_code mark; the unknown-code canary keeps its mark. Verdict: NOT_REPRODUCED.

Capture: `_test27_scenarios.txt`. All five scenarios ended in exactly one verdict.
