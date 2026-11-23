# T-298 Widget clock trust-boundary hardening (post T-297) — evidence

Scope: two independently reproduced behavioral defects after T-297 (E-3142),
Widget 0.1.05 SHA 9c7d40b9595c605e98077d77f81e0ada8e0456ca2cbb689954f780b788e4aa25.
All evidence below is synthetic (Node harness `tests/widget/harness.js`).
No live-browser (ChatGPT) acceptance performed.

## P1-A root cause (confirmed)

`resolveCurrentArchiveMetadata()` (resources/AUDAPACK_WIDGET.user.js) promoted
an unverified composer attachment into the verified canonical store whenever
`attached.timestamp > canonicalTs`:

```js
if (attached && (!canonicalTs || attached.timestamp > canonicalTs)) {
    setVerifiedProjectArchive(boundProjectId, attached);
    result = attached;
}
```

A parseable filename proves an observed timestamp, not canonical ownership.
Repro (project `audapack`, canonical `_AUDAPACK_09.10.26-T03-31-16.zip`,
unverified `_AUDAPACK_09.10.26-T08-30-00.zip`): render showed `ZIP 08:30:00`
and the verified store held the attachment; restoring canonical + re-render
overwrote it again.

## P1-B root cause (confirmed)

T-297's payload-to-turn correlation still accepted pure text equality.
Repro: hydrate history, type `continue`, failed Send (rejected, draft kept),
manually clear the draft, delayed historical `continue` turn arrives, sync —
a new `observed` Send entry was persisted though nothing was accepted.

## RED (before fix, live tree, harness)

New `tests/widget/w7-016-send-age-and-archive-timestamp.test.js` 86-89:
4/4 FAIL pre-fix with the mission signatures (`ZIP 08:30:00` overwrite;
fabricated `{provenance:'observed'}` entry; persisted clock moved).

## FIX (minimal, source-aware)

- P1-A: the bound branch never calls `setVerifiedProjectArchive` for
  attached data. Canonical verified data always wins the clock; the
  attachment stays visible only via `attachedFilename/attachedTimestamp`
  tooltip note. With no canonical authority the attachment may display,
  flagged `observedAttachment` (tooltip `Source: … (attached, unverified)`),
  and is remembered in session-local `observedArchiveByProject` (never
  persisted) for post-detach continuity. Bridge refresh path untouched:
  older-timestamp canonical replacements still accepted (identity change).
- P1-B: new capture-phase `input` listener records user-driven composer
  edits after arming (`noteComposerUserEditAfterIntent` → `intent.userEdited`).
  Corroboration refuses edited intents; sync retires them. Page-controlled
  submission consumption clears the composer without an input event, so
  genuine acceptance is unaffected. Fresh click/Enter re-arms naturally.

## GREEN (after fix)

- w7-016 89/89 (85 carried incl. T-297 A1-A10 B1-B14, updated test 39 to
  canonical-wins, new A11/A12 B15/B16).
- Full widget sweep 915/915, 0 cancelled.
- w6-006 85/85, w6-001 50/50, w3-002 14/14.
- test_bridge_project_archive.py 30/30; test_bridge.py 77 passed + 1 skip.
- Release contracts 36/36 (identity, recorder, update-probe, delivery).
- `node --check` pass; `update_widget_release.py --check` OK.
- Release 0.1.06 SHA 5136324da8a12c2f0647cb5ef5d7eceaa854f1cd487fa474068195d642e0d610.

## Preserved

T-297 closure and evidence untouched; 20 s metadata scheduler,
single-flight + backoff + generation fencing, project isolation,
change-driven verified writes, draft-stable rekey, navigation clearing,
intent window, attachment-only acceptance, receipt/authoritative paths.
