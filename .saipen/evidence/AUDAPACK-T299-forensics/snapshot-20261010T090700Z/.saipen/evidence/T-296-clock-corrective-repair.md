# T-296 Widget clock correctness repair (post T-295) — evidence

## Baseline
- Widget 0.1.03, SHA bfcfa94d55ce5095030b7249ab04c52aa538f3329637a2cc73bbceb36ec91c25 (release --check OK at start).
- T-295 evidence preserved; no T-295 files removed. Red probe: .saipen/evidence/T-296-red-probe-run.txt (0/3 on pristine HEAD bytes). Green probe: .saipen/evidence/T-296-green-probe-run.txt (3/3 after fix).

## Confirmed defects and root causes
1. TARGET A — `syncSendTrackerFromDOM()` classified hydration via ID substrings (`currentKey.includes('hydrat')`, `turnId.includes('hist')`); regression fixtures (`c:stable-hydrating-chat`, `hist-turn-1`) concealed it. Three branches fell back to `Date.now()` for unverified Sends (existing-entry turn change, empty-baseline first turn, subsequent new turn).
2. TARGET B — ZIP metadata refresh reachable only via indicator rendering; per-second Send ticker renders Send only, so idle visible widget never revalidated canonical archive metadata (measured 0 requests over 35 s idle).
3. TARGET C — tests 07/19/20 treated any new DOM turn as a Send without acceptance evidence; harness `FakeElement.click()/dispatchEvent()` never reached document-level delegated listeners and `FakeEvent` carried no keyboard fields, so the delegated Send path was untested.

## Functions modified (resources/AUDAPACK_WIDGET.user.js)
- `trackManualSendAttempt` (+`snapshotComposerForSendIntent`, `withoutManualSendIntent`, `widgetSendDispatchDepth`): composer baseline snapshot; widget-initiated dispatches suppressed.
- `peekManualSendIntent`, `consumeManualSendIntent`, `liveComposerPayloadDeparted`, `manualSendIntentCorroborated`: intent+turn+composer correlation (all three required).
- `syncSendTrackerFromDOM`: rewritten trust contract; no ID substrings; no `Date.now()` fallback; authoritative/receipt > entry adopted; persisted entries preserved otherwise.
- `recordSendObservation`: explicit timestamp required (no `Date.now()` fallback).
- `dispatchElementClick`, `clickChatGPTSendVerified`, `submitChatGPTComposerFormVerified`, `triggerSend` Enter fallback: intent suppression.
- `refreshProjectArchiveMetadata` success path: equal data no longer rewrites storage (`>` instead of `>=`).
- New: `currentBoundProjectIdForMetadataPoll`, `maybeRefreshArchiveMetadataBackground`, `scheduleArchiveMetadataPoll`, `startArchiveMetadataPoll`, `cancelArchiveMetadataPoll`, `ARCHIVE_METADATA_POLL_INTERVAL_MS=20000`; wired into `mount()`, `visibilitychange` (hidden cancels, foreground catches up), `manualArchiveRecordSent` (post-generation bounded validation); test-API exports added.
- Harness (tests/widget/harness.js): capture→target→bubble propagation with capture flags; `FakeEvent` keyboard fields.
- Tests: w7-016 45→61 (rewrote 06/07/19/20/21/28, added 46–61, UUID fixtures, wall-clock stubs); w3-002 fixed 2 stale pre-T-295 expectations (`ZIP 5m`→`ZIP 00:05:00`, `filename`→`archive filename`).

## Results
- w7-016 61/61, w6-006 85/85, w6-001 50/50, test_bridge_project_archive.py 30/30.
- Adjacent: w4-004 24/24, w6-004 59/59, w7-011 7/7, w6-003 15/15, w2-003 6/6, perf-004/011/002/009 green, w7-012 14/14, w7-008 16/16, w3-002 14/14.
- Full per-file sweep: 882 pass; 2 anomalies resolved (w3-002 stale format fixed; w6-002 sweep-only 48/47/1 under parallel load, 51/51/0 x3 idle).
- Idle refresh: 3–4 bounded metadata requests per 70 s idle; 0 requests while hidden; 0 GM writes on unchanged data; single timer, no per-second scans.
- node --check, ruff, compileall, update_widget_release.py --check: clean.
- Live Chromium/ChatGPT smoke: NOT practical here (no Bridge/worker fleet in this environment); no Brave/human acceptance claimed. Synthetic harness now exercises the genuine document-level delegated path.

## Release
- Version 0.1.04, SHA-256 2cb1bf60c8eed566b1077b7567aa3223c7b756daa1a7718ef4dfa604052b27e4 (recorded + verified, Bridge delivery identity 30/30).
