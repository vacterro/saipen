# T-299 — Widget 0.1.07 Trust-Boundary Hardening (P1-A + P1-B)

## Ticket identity
- **T-299** — Widget clock trust-boundary hardening post T-298
- Widget version: 0.1.06 → 0.1.07
- SHA-256 (0.1.07): `5efa3a49fee7bdef83f63ecfa3324e2746eb12b874baad4e1bba03edd03a09fa`
- Owner: buffy
- Closure mode: own_patch

## P1-A: Receipt must NOT overwrite canonical archive metadata

### Defect
`manualArchiveRecordSent()` (resources/AUDAPACK_WIDGET.user.js:20899) previously
called `setVerifiedProjectArchive()` with the receipt's filename, treating a Send
receipt as canonical authority. A receipt proves transmission only.

### Fix
Removed the `setVerifiedProjectArchive` call. Receipt now:
1. Calls `recordSendObservation(key, { timestamp: entry.at, provenance: 'receipt' })`
   — updates the SEND tracker timestamp only.
2. Calls `refreshProjectArchiveMetadata(project, { background: true })` — bounded
   Bridge validation that can adopt canonical metadata only if the Bridge
   confirms it. Zero canonical-store writes from the receipt itself.

### Tests (C1–C10, w7-016)
All C-series tests assert canonical store is untouched by receipts:

| Test | Assertion | Result |
|------|-----------|--------|
| C1 | Older receipt doesn't overwrite newer Bridge canonical | PASS |
| C2 | Newer receipt doesn't overwrite older Bridge canonical | PASS |
| C3 | Receipt updates SEND timestamp | PASS |
| C4 | Idempotent receipts perform zero canonical writes | PASS |
| C5 | Receipt identity preserved separately from canonical | PASS |
| C6 | Receipt filename never lands in canonical store | PASS |
| C7 | Bridge-confirmed older archive replacement after receipt | PASS |
| C8 | Bridge offline preserves confirmed metadata despite receipt | PASS |
| C9 | Cross-project isolation: Project A receipt can't touch B | PASS |
| C10 | Manual receipt and automatic archive coexist | PASS |

**RED signatures**: all 10 C-tests fail against the pre-fix code (receipt writes
canonical store, violating P1-A).

**GREEN result**: 110/110 w7-016 tests pass after fix.

## P1-B: Rejected attachment-only Send + manual removal + delayed history must NOT fabricate accepted Send timestamp

### Defect
Attachment-only Sends carry no text to correlate. The `input` event listener
(`noteComposerUserEditAfterIntent`) did not fire on attachment tile removal
(mouse click or keyboard activation), so a rejected attachment-only Send +
delayed same-text history could fabricate an accepted Send timestamp via
`manualSendIntentCorroborated`.

### Fix
1. Added `noteComposerAttachmentRemoved(removeButton)` (line ~21013): marks
   `intent.userEdited = true` only when the operator actually interacts with a
   removal control (positive evidence via event target).
2. Added `attachmentRemovalIntentInstalled` flag (line ~20953): guards one-shot
   installation of the document-level capture-phase listeners.
3. Capture-phase `click` listener on `document` detecting
   `button[aria-label^="Remove" i]` within composer root.
4. Capture-phase `keydown` listener for Enter/Space on remove buttons.
5. Extended `retireStaleManualSendIntent` to check tile count changes for
   attachment-only intents (empty composerText) — handles React remount
   (D8) where no click/keydown event fires.

### Tests (D1–D11, w7-016)

| Test | Assertion | Result |
|------|-----------|--------|
| D1 | Failed attachment-only Send + mouse removal + delayed history fabricates nothing | PASS |
| D2 | Cancelled attachment-only intent preserves previous SEND timestamp | PASS |
| D3 | Attachment replacement invalidates pending intent | PASS |
| D4 | Genuine accepted attachment-only Send still records | PASS |
| D5 | Programmatic tile consumption during accepted Send is not cancellation | PASS |
| D6 | Document-delegated removal invalidates pending intent without input event | PASS |
| D7 | Keyboard activation of removal control invalidates intent | PASS |
| D8 | React remount (tile disconnected without removal event) fabricates nothing | PASS |
| D9 | Navigation invalidates stale attachment-only intent | PASS |
| D10 | Draft-to-stable migration keeps cancelled intent cancelled | PASS |
| D11 | Repeated identical filenames preserve transaction identity | PASS |

**RED signatures**: all 11 D-tests fail against the pre-fix code.

**GREEN result**: 110/110 w7-016 tests pass after fix.

## Regression gates

| Gate | Result |
|------|--------|
| tests/widget/w7-016-send-age-and-archive-timestamp.test.js | 110/110 PASS, 0 fail |
| tests/widget/w6-006-manual-archive-picker.test.js | 85/85 PASS, 0 fail |
| tests/widget/w6-001-auto-archive.test.js | 50/50 PASS, 0 fail |
| tests/widget/w3-002-fresh-archive-autostart.test.js | 14/14 PASS, 0 fail |
| tests/widget/w7-011-submit-without-send-control.test.js | 7/7 PASS, 0 fail |
| tests/widget/w7-015-attachment-chrome-pollution.test.js | 5/5 PASS, 0 fail |
| tests/test_bridge_project_archive.py | 30/30 PASS |
| Full widget suite (node --test tests/widget/*.test.js) | 772/772 PASS, 0 fail |

## Release identity

```
scripts/update_widget_release.py --check
OK: 0.1.07 5efa3a49fee7bdef83f63ecfa3324e2746eb12b874baad4e1bba03edd03a09fa
```

### Red control (T-196 invariant)
Appending one comment line to the shipped widget makes `update_widget_release.py`
refuse with `VERSION_NOT_INCREASED`. The invariant holds: no bytes change
without a version bump.

## Performance acceptance
- Full widget suite: 772 tests in 130.3s (avg 168 ms/test)
- Test runner lifecycle: clean process exit, 0 cancelled, 0 timer leaks
- no timers survive teardown (harness FakeTimers restored)

## LIVE browser acceptance
Not claimed — human-operated Tampermonkey install remains in
docs/AUDAPACK_WIDGET_ACCEPTANCE.md. The machine-verifiable half is proven by
772 synthetic tests across the full widget test suite.
