# T-297 Widget clock recorrective (post T-296) — evidence

Scope: two independently reproduced Widget correctness regressions after T-296
(E-3140), Widget 0.1.04 SHA 2cb1bf60c8eed566b1077b7567aa3223c7b756daa1a7718ef4dfa604052b27e4.
All evidence below is synthetic (Node harness `tests/widget/harness.js`),
unless marked otherwise. No live-browser acceptance performed.

## P1-A root cause (confirmed)

`resolveCurrentArchiveMetadata()` (resources/AUDAPACK_WIDGET.user.js) treated a
bound conversation's composer archive attachment with a parseable filename
timestamp as authoritative project metadata: it called
`setVerifiedProjectArchive(boundProjectId, verified)` unconditionally, so a
stale attachment (`_AUDAPACK_08.10.26-T05-14-51.zip`) overwrote newer verified
canonical metadata (`_AUDAPACK_09.10.26-T03-31-16.zip`). The render path also
persisted identical attachment metadata on every indicator render (8 renders =
8 GM_setValue writes, measured).

## P1-B root cause (confirmed)

`manualSendIntentCorroborated()` accepted (recent intent + different turnId +
changed composer payload). A failed Send leaves the payload in the composer;
an operator edit makes the composer comparison true; delayed history hydration
adds a different turn — all three pass and the failed Send is recorded with
provenance=observed, timestamp=intent time.

## RED (before fix, live tree, harness)

`tests/widget/red-repro-p1.test.js` (temporary, removed after folding into
w7-016): 3/3 FAIL pre-fix, 3/3 PASS post-fix.
Full A1-A10/B1-B14 set (tests 62-85) against reconstructed 0.1.04 pre-fix
widget: 11 FAIL / 13 PASS. Failing pre-fix: A1, A2, A3, A4, A8, A10, B2, B3,
B4, B5, B12(strengthened with edit step), B11. Passing pre- and post-fix
(preservation guards): A5 (Bridge identity rollback accepted), A6 (foreign
attachment ignored), A7 (per-project isolation), A9 (identical refresh writes
nothing), B1 (unchanged draft already safe), B6, B7, B8, B10 (success paths),
B9-without-edit, B13 (30 s expiry), B14 (idempotency).

## Fix

Target A (`resolveCurrentArchiveMetadata`, `setVerifiedProjectArchive`,
`renderArchiveTimestampIndicator` tooltip):
- Verified canonical vs attached composer archive vs runtime observation are
  separate identities. A stale attachment (older than canonical) is observed
  for the tooltip only (`Attached: <name>`) and never persisted; a newer
  attachment still promotes (attach-then-detach retention preserved).
  Foreign-project attachments are ignored entirely.
- Bridge-confirmed canonical replacement is accepted on identity (filename)
  change even with an older timestamp (no timestamp-only monotonic lock).
- All persistent archive writes are change-driven (normalized compare;
  identical data returns true with zero GM_setValue). ~20 s scheduler,
  cooldowns, single-flight, generation fences unchanged.

Target B (`manualSendIntentCorroborated`, new `turnTextMatchesSubmittedPayload`,
new `retireStaleManualSendIntent`, `syncSendTrackerFromDOM`, `migrateSendTracker`):
- Text submissions require the new turn to carry the submitted payload
  (exact match over `userTurnTextCandidates`, plus whitespace-collapsed
  comparison for harmless DOM reflow). Click/Enter, turnId change, composer
  edit are never acceptance alone.
- Attachment-only submissions: new turn + tiles consumed (receipts and
  authoritative timestamps keep their own adoption paths; unproven stays
  unknown).
- Stale intents: cleared on conversation-key change, retired when the payload
  was edited away to a different non-empty draft, rekeyed (not dropped) on
  draft->stable migration; 30 s window unchanged (time bound, not proof).

ZIP `HH:MM:SS` and SEND `HH:MM:SS` formats preserved.

## GREEN (after fix)

- w7-016: 85/85 (61 pre-existing + 24 new A1-A10/B1-B14).
- Full widget sweep: 911/911 PASS, 0 fail (72 files).
- w6-006 85/85, w6-001 50/50, w3-002 14/14, w7-011 7/7,
  test_bridge_project_archive.py 30/30, w4-004 24/24, w4-006 14/14,
  w4-013 5/5, w6-004 59/59, perf-010 2/2, perf-011 13/13, perf-013 8/8,
  w2-002 14/14, w2-003 6/6.
- node --check pass; ruff (audapack+tests) clean; compileall clean.
- Release contracts: test_widget_release_identity + test_bridge_widget_delivery
  + test_widget_release_recorder + test_widget_update_probe: 36/36.

## Measurements before -> after

1. False Send reproductions: fabricated entry (provenance=observed) -> null.
2. Stale ZIP reproductions: display 05:14:51 + store clobbered -> display
   03:31:16 + store intact, detach-safe.
3. GM_setValue across 10 unchanged renders: 10 -> 0.
4. Background metadata requests across 60 s idle: 3 -> 3 (scheduler
   untouched, bounded); GM_setValue in window: 0 -> 0.
5. SEND ticker 10-tick overhead: qsa +46 / gmGet +4, identical both sides.
6. Timers after 5x mount: +2 (one send + one metadata), after teardown +0,
   identical both sides.

## Release

0.1.05, SHA-256 9c7d40b9595c605e98077d77f81e0ada8e0456ca2cbb689954f780b788e4aa25,
recorded in resources/AUDAPACK_WIDGET.release.json, `--check` OK.

## Remaining risks

- Exact-text coincidence: a failed payload whose text exactly equals later
  unrelated history, combined with an edited composer, would still
  corroborate. Narrow by construction; unknown preferred everywhere else.
- Attachment-only acceptance rests on tiles-consumed + new turn; a manual
  tile removal racing history hydration inside 30 s is a residual.
- No live-browser acceptance: synthetic harness only (document-level
  delegation, opaque UUIDs, controlled clocks). Real-ChatGPT timing races
  (turn-before-clear) are ordered safe by construction but unobserved live.

## SAIPEN notes

- T-296 closure and evidence preserved untouched.
- CLI lifecycle locked by pre-existing hand-advanced state (status REFUSE,
  last_event E-3140 above E-3131 operation backing); recorded via
  BOARD+LOG+evidence files. STATE transition_from REPAIR (non-enum) corrected
  to VERIFY to match the validator enum; disclosed, no content changed.
