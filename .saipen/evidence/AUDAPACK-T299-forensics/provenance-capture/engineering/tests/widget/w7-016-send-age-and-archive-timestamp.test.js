'use strict';

const { test } = require('node:test');
const assert = require('node:assert');
const {
  setup,
  mainEl,
  userTurn,
  assistantTurn,
  addTurns,
  composerFixture,
  addComposerAttachmentTile,
  installAcceptedSend,
  runtimeFixture,
  FakeEvent
} = require('./helpers');

test('W7-016 01: New conversation shows SEND —', async () => {
  const { h, api } = setup();
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.ok(sendAgeEl, '#acb-send-age indicator element exists');
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAgeEl.textContent, 'SEND —');
  assert.ok(sendAgeEl.title.includes('No send recorded'));
});

test('W7-016 02: Confirmed message updates SEND', async () => {
  const { h, api } = setup();
  const now = Date.now();
  const currentKey = api.currentConversationKey();

  api.recordSendObservation(currentKey, {
    timestamp: now - 120000,
    turnId: 'turn-user-1',
    provenance: 'authoritative'
  });

  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:02:00');
  assert.ok(sendAgeEl.title.includes('Provenance: authoritative'));
  assert.ok(sendAgeEl.title.includes('Turn ID: turn-user-1'));
  assert.ok(sendAgeEl.title.includes('Age: 2 minutes'));
});

test('W7-016 03: Failed Send does not reset elapsed time', async () => {
  const { h, api } = setup();
  const now = Date.now();
  const currentKey = api.currentConversationKey();
  const initialSendTime = now - 300000; // 5 min ago

  api.recordSendObservation(currentKey, {
    timestamp: initialSendTime,
    turnId: 'turn-user-0',
    provenance: 'observed'
  });

  const fixture = composerFixture(h);
  fixture.send._sendFails = true; // Simulates failure
  fixture.input.textContent = 'Failed message';

  const result = await api.triggerSend({ key: 'chatgpt', allowEnterFallback: true }, fixture.input, {
    waitForReadyMs: 0
  });

  assert.strictEqual(result.ok, false);
  const entry = api.getSendTrackerEntry(currentKey);
  assert.strictEqual(entry.timestamp, initialSendTime, 'Timestamp must remain at initialSendTime');
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:05:00');
});

test('W7-016 04: Automatic ZIP Send updates only after acceptance', async () => {
  const { h, api } = setup();
  const currentKey = api.currentConversationKey();
  assert.strictEqual(api.getSendTrackerEntry(currentKey), null);

  const receipt = {
    conversationKey: currentKey,
    projectId: 'audapack',
    sha256: 'a1b2c3d4e5f60000000000000000000000000000000000000000000000000000',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  };

  const ok = api.manualArchiveRecordSent(receipt);
  assert.strictEqual(ok, true);

  const entry = api.getSendTrackerEntry(currentKey);
  assert.ok(entry, 'Entry recorded after acceptance');
  assert.strictEqual(entry.provenance, 'receipt');

  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:00:00');
});

test('W7-016 05: Attach-only never resets SEND', async () => {
  const { h, api } = setup();
  const now = Date.now();
  const currentKey = api.currentConversationKey();
  const initialSendTime = now - 600000; // 10 min ago

  api.recordSendObservation(currentKey, {
    timestamp: initialSendTime,
    turnId: 'turn-user-1',
    provenance: 'observed'
  });

  const fixture = composerFixture(h);
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  h.mutate(fixture.form);

  const entry = api.getSendTrackerEntry(currentKey);
  assert.strictEqual(entry.timestamp, initialSendTime, 'Timestamp unchanged by attach-only');
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:10:00');
});

test('W7-016 06: Repeated observation of one turn is idempotent', async () => {
  const { h, api } = setup();
  // Authoritative server timestamp: positive evidence, adopted exactly once.
  const authTs = Date.now() - 120000;
  const turn = userTurn(h, 'a1b2c3d4-1111-4222-8333-444444444444', 'Hello ChatGPT');
  turn.setAttribute('data-timestamp', String(authTs));
  addTurns(h, [turn]);

  api.syncSendTrackerFromDOM();
  const entry1 = api.getSendTrackerEntry();
  assert.ok(entry1);
  assert.strictEqual(entry1.timestamp, authTs);
  assert.strictEqual(entry1.provenance, 'authoritative');

  // Advance time
  h.advance(60000);

  api.syncSendTrackerFromDOM();
  const entry2 = api.getSendTrackerEntry();

  assert.strictEqual(entry1?.timestamp, entry2?.timestamp, 'Repeated observation keeps same timestamp');
  assert.strictEqual(entry2.provenance, 'authoritative');
});

test('W7-016 07: History hydration fabricates nothing; only an accepted Send records', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();

  const turn = userTurn(h, 'b2c3d4e5-2222-4222-8333-555555555555', 'Old conversation history message');
  addTurns(h, [turn]);

  // First sync simulates hydration
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry();
  assert.strictEqual(entry, null, 'No entry fabricated for historical turn');
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAgeEl.textContent, 'SEND —');

  // A second historical chunk arriving later is still not a Send: a new DOM
  // turn WITHOUT local Send evidence must not move the clock. (T-296: the
  // previous revision of this test treated any new turn as a Send.)
  const laterHistory = userTurn(h, 'c3d4e5f6-3333-4222-8333-666666666666', 'More old history');
  addTurns(h, [laterHistory]);

  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(), null, 'Unproven turn must not create a Send entry');

  // Only a genuinely accepted Send (operator intent + accepted turn/composer
  // transition through the document-level delegated path) records.
  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.input.textContent = 'New user query';
  fixture.send.click();

  api.syncSendTrackerFromDOM();
  const updatedEntry = api.getSendTrackerEntry();
  assert.ok(updatedEntry, 'Accepted Send receives observation timestamp');
  assert.strictEqual(updatedEntry.provenance, 'observed');
  assert.ok(updatedEntry.timestamp > 0);
});

test('W7-016 08: Reload preserves known timestamps', async () => {
  const { h, api } = setup();
  const currentKey = api.currentConversationKey();
  const sendTime = Date.now() - 3600000; // 1 hour ago

  api.setSendTrackerEntry(currentKey, {
    timestamp: sendTime,
    turnId: 'persisted-turn',
    provenance: 'authoritative'
  });

  // Verify stored in GM
  const rawStore = h.sandbox.GM_getValue('audapack_send_tracker_v1', '');
  assert.ok(rawStore.includes('persisted-turn'));

  // Re-render
  api.renderTitlebarIndicators();
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND 01:00:00');
});

test('W7-016 09: Changing chats restores each chat\'s own send age', async () => {
  const { h, api } = setup();
  const now = Date.now();

  api.setSendTrackerEntry('c:chat-alpha', {
    timestamp: now - 900000, // 15m
    turnId: 'turn-a',
    provenance: 'authoritative'
  });

  api.setSendTrackerEntry('c:chat-beta', {
    timestamp: now - 180000, // 3m
    turnId: 'turn-b',
    provenance: 'authoritative'
  });

  // On chat alpha
  h.sandbox.location.pathname = '/c/chat-alpha';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  api.renderTitlebarIndicators();
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:15:00');

  // Switch to chat beta
  h.sandbox.location.pathname = '/c/chat-beta';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:03:00');

  // Switch back to chat alpha
  h.sandbox.location.pathname = '/c/chat-alpha';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:15:00');
});

test('W7-016 10: Switching projects updates ZIP independently', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();

  const tsA = Date.parse('2026-10-08T05:14:51');
  const tsB = Date.parse('2026-10-08T08:30:00');

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip',
    timestamp: tsA,
    source: 'archive filename'
  });

  api.setVerifiedProjectArchive('fastprompter', {
    filename: '_FASTPROMPTER_08.10.26-T08-30-00.zip',
    timestamp: tsB,
    source: 'archive filename'
  });

  // Bind to audapack
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, api.formatArchiveTimestampClock(tsA));
  assert.ok(zipEl.title.includes('Archive: AUDAPACK'));
  assert.ok(zipEl.title.includes('Source: archive filename'));

  // Switch to fastprompter
  api.setManualArchiveBinding({ project_id: 'fastprompter', display_name: 'FastPrompter' });
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, api.formatArchiveTimestampClock(tsB));
  assert.ok(zipEl.title.includes('Archive: FastPrompter'));
});

test('W7-016 11: Archive timestamp parses correctly from filename', async () => {
  const { h, api } = setup();

  const fn1 = '_AUDAPACK_08.10.26-T05-14-51(1).zip';
  const meta1 = { filename: fn1, source: 'archive filename' };
  api.setVerifiedProjectArchive('proj1', meta1);
  const stored1 = api.getVerifiedProjectArchive('proj1');

  assert.ok(stored1.timestamp > 0);
  const clock = api.formatArchiveTimestampClock(stored1.timestamp);
  assert.strictEqual(clock, 'ZIP 05:14:51');

  const dtStr = api.formatArchiveTimestampDateTime(stored1.timestamp);
  assert.strictEqual(dtStr, '08.10.2026 05:14:51');
});

test('W7-016 12: Unknown timestamp shows ZIP —', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();

  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP —');
  assert.ok(zipEl.title.includes('No archive timestamp available'));
});

test('W7-016 13: Bridge mtime is not misrepresented as creation time', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();

  const mtimeTs = Date.parse('2026-10-08T07:22:15');
  api.setVerifiedProjectArchive('audapack', {
    filename: 'audapack_repo.zip', // No timestamp in filename
    timestamp: mtimeTs,
    source: 'bridge mtime',
    mtime: Math.floor(mtimeTs / 1000)
  });

  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  api.renderTitlebarIndicators();

  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, api.formatArchiveTimestampClock(mtimeTs));
  assert.ok(zipEl.title.includes('Last modified:'), 'Tooltip must use "Last modified" for bridge mtime');
  assert.ok(!zipEl.title.includes('Timestamp:'), 'Tooltip must NOT use "Timestamp:" label for bridge mtime');
  assert.ok(!zipEl.title.includes('Created:'), 'Tooltip must NOT use "Created" for bridge mtime');
  assert.ok(zipEl.title.includes('Source: bridge mtime'));
});

test('W7-016 14: Detaching a sent ZIP preserves its last verified time', async () => {
  const { h, api } = setup();
  const fixture = composerFixture(h);
  const currentKey = api.currentConversationKey();

  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });

  api.manualArchiveRecordSent({
    conversationKey: currentKey,
    projectId: 'audapack',
    sha256: '9999888877776666555544443333222211110000111122223333444455556666',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  });

  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 05:14:51');

  // Detach tile
  tile.remove();
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 05:14:51', 'Detaching tile preserves verified archive timestamp');
});

test('W7-016 15: Super Compact keeps both indicators readable', async () => {
  const { h, api } = setup();
  const panel = h.dom.querySelector('#acb-popup');
  assert.ok(panel);

  api.state.superCompact = true;
  api.mount();
  panel.dataset.supercompact = 'true';
  api.renderTitlebarIndicators();

  const indicators = h.dom.querySelector('#acb-title-indicators');
  const sendAge = h.dom.querySelector('#acb-send-age');
  const zipTs = h.dom.querySelector('#acb-archive-timestamp');

  assert.ok(indicators, '#acb-title-indicators exists in supercompact');
  assert.ok(sendAge, '#acb-send-age exists in supercompact');
  assert.ok(zipTs, '#acb-archive-timestamp exists in supercompact');
  assert.notStrictEqual(indicators.style.display, 'none');
  assert.strictEqual(sendAge.textContent, 'SEND —');
  assert.strictEqual(zipTs.textContent, 'ZIP —');
});

test('W7-016 16: Repeated mount/navigation creates no timer leaks', async () => {
  const { h, api } = setup();

  api.startSendAgeTimer();
  assert.strictEqual(api.isSendAgeTimerActive, true);

  // Calling startSendAgeTimer repeatedly should cancel old and schedule single new timer
  api.startSendAgeTimer();
  api.startSendAgeTimer();
  assert.strictEqual(api.isSendAgeTimerActive, true);

  api.cancelSendAgeTimer();
  assert.strictEqual(api.isSendAgeTimerActive, false);
});

test('W7-016 17: Existing archive freshness reporting still works', async () => {
  const { h, api } = setup();
  const fixture = composerFixture(h);

  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  const freshness = api.resolveCurrentArchiveMetadata();
  assert.ok(freshness);
  assert.strictEqual(freshness.filename, '_AUDAPACK_08.10.26-T05-14-51.zip');
  assert.ok(freshness.timestamp > 0);
  assert.strictEqual(freshness.source, 'archive filename');
});

test('W7-016 18: Existing ZIP-send receipts remain unchanged', async () => {
  const { h, api } = setup();
  const receipt = {
    conversationKey: 'c:receipt-chat',
    projectId: 'audapack',
    sha256: 'deadbeef0000111122223333444455556666777788889999aaaabbbbccccdddd',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip',
    payloads: ['payload1']
  };

  const saved = api.manualArchiveRecordSent(receipt);
  assert.strictEqual(saved, true);

  const store = api.manualArchiveSentStore();
  assert.strictEqual(store.version, 1);
  const found = store.entries.find(e => e.key === 'c:receipt-chat');
  assert.ok(found);
  assert.strictEqual(found.project_id, 'audapack');
  assert.strictEqual(found.sha256, receipt.sha256);
  assert.strictEqual(found.filename, receipt.filename);
  assert.ok(found.at > 0);
});

test('W7-016 19: Empty conversation -> first accepted manual Send', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  h.sandbox.location.pathname = '/'; // true new draft

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);

  // Initially empty conversation
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(), null);
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAgeEl.textContent, 'SEND —');

  // A bare turn with no local Send evidence is NOT a Send.
  const strayTurn = userTurn(h, 'd4e5f6a7-4444-4222-8333-777777777777', 'Stray turn, no intent');
  addTurns(h, [strayTurn]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(), null, 'Unproven turn must not record a Send');
  strayTurn.remove();

  // First accepted manual Send: operator intent + accepted turn/composer
  // transition through the document-level delegated path.
  fixture.input.textContent = 'First question';
  fixture.send.click();

  api.syncSendTrackerFromDOM();
  const entry = api.getSendTrackerEntry();
  assert.ok(entry, 'First accepted manual Send must be recorded');
  assert.strictEqual(entry.provenance, 'observed');
  assert.ok(entry.timestamp > 0);

  api.renderTitlebarIndicators(entry.timestamp);
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:00:00');
});

test('W7-016 20: Empty conversation -> multiple accepted Sends reset counter', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  h.sandbox.location.pathname = '/'; // true new draft
  // Controlled wall-clock together with fake timers.
  let fakeNow = Date.now();
  h.sandbox.Date.now = () => fakeNow;

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);

  // Initially empty
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(), null);

  // First accepted send
  fixture.input.textContent = 'First query';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const entry1 = api.getSendTrackerEntry();
  assert.ok(entry1, 'First accepted Send recorded');
  const t1 = entry1.timestamp;

  // Advance wall-clock and fake timers by 35 seconds
  fakeNow += 35000;
  h.advance(35000);
  api.renderTitlebarIndicators(t1 + 35000);
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:00:35');

  // Second accepted send
  fixture.input.textContent = 'Second query';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const entry2 = api.getSendTrackerEntry();
  assert.ok(entry2, 'Second accepted Send recorded');
  assert.ok(entry2.timestamp > t1, 'Second send timestamp is newer');

  api.renderTitlebarIndicators(entry2.timestamp);
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:00:00');
});

test('W7-016 21: Draft -> stable route migration without binding', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();

  // Setup draft conversation
  h.sandbox.location.pathname = '/';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  const draftKey = api.currentConversationKey();
  assert.ok(draftKey.startsWith('draft:'));

  // Ensure no project binding
  assert.strictEqual(api.manualArchiveBindingFor(draftKey), null);

  // Accepted Send in draft (operator intent + accepted turn/composer transition)
  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.input.textContent = 'Draft query';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const draftEntry = api.getSendTrackerEntry(draftKey);
  assert.ok(draftEntry, 'Accepted draft Send recorded before migration');
  const sendTs = draftEntry.timestamp;

  // ChatGPT assigns stable /c/... route
  h.sandbox.location.pathname = '/c/c-chat-stable-123';
  const stableKey = api.currentConversationKey();
  assert.strictEqual(stableKey, 'c:c-chat-stable-123');

  // Route transition runs bindAutoRuntimeToCurrentConversation
  api.bindAutoRuntimeToCurrentConversation({ claim: false });

  // Verify migration without binding
  const stableEntry = api.getSendTrackerEntry(stableKey);
  assert.ok(stableEntry, 'Send tracker migrated to stable route without project binding');
  assert.strictEqual(stableEntry.timestamp, sendTs);
  assert.strictEqual(api.getSendTrackerEntry(draftKey), null, 'Draft key cleaned up');

  api.renderTitlebarIndicators(sendTs + 65000);
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:01:05');
});

test('W7-016 22: Real elapsed seconds and hour/day transitions', async () => {
  const { api } = setup();
  assert.strictEqual(api.compactElapsedAge(0), '00:00:00');
  assert.strictEqual(api.compactElapsedAge(1000), '00:00:01');
  assert.strictEqual(api.compactElapsedAge(755000), '00:12:35');
  assert.strictEqual(api.compactElapsedAge(5048000), '01:24:08');
  assert.strictEqual(api.compactElapsedAge(86400000), '1d 00:00:00');
  assert.strictEqual(api.compactElapsedAge(90065000), '1d 01:01:05');
  assert.strictEqual(api.compactElapsedAge(172800000 + 7200000 + 180000 + 4000), '2d 02:03:04');
});

test('W7-016 23: Background tab and foreground resumption', async () => {
  const { h, api } = setup();

  api.startSendAgeTimer();
  assert.strictEqual(api.isSendAgeTimerActive, true);

  // Background tab: document becomes hidden
  h.sandbox.document.hidden = true;
  h.sandbox.document.dispatchEvent(new FakeEvent('visibilitychange'));
  assert.strictEqual(api.isSendAgeTimerActive, false, 'Timer cancelled when tab is hidden');

  // Foreground: document becomes visible again
  h.sandbox.document.hidden = false;
  h.sandbox.document.dispatchEvent(new FakeEvent('visibilitychange'));
  assert.strictEqual(api.isSendAgeTimerActive, true, 'Timer resumed when tab becomes visible');

  api.cancelSendAgeTimer();
});

test('W7-016 24: Timestamp priority: filename versus mtime', async () => {
  const { api } = setup();
  api.clearVerifiedProjectArchives();

  const fnTs = Date.parse('2026-10-08T22:21:49');
  const mtimeTs = Date.parse('2026-10-08T05:00:00');

  api.setVerifiedProjectArchive('proj-priority', {
    filename: '_AUDAPACK_08.10.26-T22-21-49.zip',
    timestamp: mtimeTs,
    mtime: Math.floor(mtimeTs / 1000)
  });

  const verified = api.getVerifiedProjectArchive('proj-priority');
  assert.strictEqual(verified.timestamp, fnTs, 'Filename timestamp must override mtime');
  assert.strictEqual(verified.source, 'archive filename');
});

test('W7-016 25: Invalid timestamp and unknown metadata', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();

  // Invalid month 13
  assert.strictEqual(api.archiveTimestampFromFilename('_AUDAPACK_08.13.26-T22-21-49.zip'), 0);
  // Invalid day 32
  assert.strictEqual(api.archiveTimestampFromFilename('_AUDAPACK_32.10.26-T22-21-49.zip'), 0);
  // Invalid hour 25
  assert.strictEqual(api.archiveTimestampFromFilename('_AUDAPACK_08.10.26-T25-21-49.zip'), 0);
  // Invalid minute 60
  assert.strictEqual(api.archiveTimestampFromFilename('_AUDAPACK_08.10.26-T22-60-49.zip'), 0);
  // Arbitrary non-timestamp filename
  assert.strictEqual(api.archiveTimestampFromFilename('some-random-file.zip'), 0);

  // Set malformed archive metadata
  api.setVerifiedProjectArchive('proj-bad', {
    filename: '_AUDAPACK_08.13.26-T22-21-49.zip',
    source: 'unknown'
  });

  api.setManualArchiveBinding({ project_id: 'proj-bad', display_name: 'ProjBad' });
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP —');
});

test('W7-016 26: Archive replacement and detached attachment', async () => {
  const { h, api } = setup();
  const fixture = composerFixture(h);
  api.clearVerifiedProjectArchives();

  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });

  // Attach first archive
  const tile1 = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 05:14:51');

  // Replace with second archive
  tile1.remove();
  const tile2 = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T22-21-49.zip');
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 22:21:49');

  // Detach tile2
  tile2.remove();
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 22:21:49', 'Detaching preserves latest replaced archive timestamp');
});

test('W7-016 27: Normal, collapsed, and Super Compact geometry', async () => {
  const { h, api } = setup();
  const panel = h.dom.querySelector('#acb-popup');
  assert.ok(panel);

  const indicators = h.dom.querySelector('#acb-title-indicators');
  const sendAge = h.dom.querySelector('#acb-send-age');
  const zipTs = h.dom.querySelector('#acb-archive-timestamp');

  // Normal mode
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAge.textContent, 'SEND —');
  assert.strictEqual(zipTs.textContent, 'ZIP —');
  assert.notStrictEqual(indicators.style.display, 'none');

  // Collapsed mode
  panel.dataset.collapsed = 'true';
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAge.textContent, 'SEND —');
  assert.strictEqual(zipTs.textContent, 'ZIP —');
  assert.notStrictEqual(indicators.style.display, 'none');

  // Super Compact mode
  panel.dataset.collapsed = 'false';
  panel.dataset.supercompact = 'true';
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAge.textContent, 'SEND —');
  assert.strictEqual(zipTs.textContent, 'ZIP —');
  assert.notStrictEqual(indicators.style.display, 'none');
});

test('W7-016 28: Stable chat initially renders empty, then old history hydrates', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  // Opaque UUID fixtures: no id substring may imply hydration or history.
  const convo = 'c:e5f6a7b8-5555-4222-8333-888888888888';
  h.sandbox.location.pathname = '/c/e5f6a7b8-5555-4222-8333-888888888888';

  // 1. Initial render with empty DOM (before history has loaded)
  api.syncSendTrackerFromDOM();
  api.renderTitlebarIndicators();
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  assert.strictEqual(sendAgeEl.textContent, 'SEND —');
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'Must not fabricate baseline on unhydrated stable chat');

  // 2. Old history message hydrates later
  const oldTurn = userTurn(h, 'f6a7b8c9-6666-4222-8333-999999999999', 'Historical query');
  addTurns(h, [oldTurn]);

  api.syncSendTrackerFromDOM();
  api.renderTitlebarIndicators();

  // 3. SEND must still be unknown, not reset to Date.now()!
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'Historical turn hydration must not create observed send entry');
  assert.strictEqual(sendAgeEl.textContent, 'SEND —');
});

test('W7-016 29: True new conversation accepts its first manual Send', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  h.sandbox.location.pathname = '/'; // draft chat

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);

  // Initially empty draft
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(), null);

  // User types and submits message
  fixture.input.textContent = 'Hello new world';
  fixture.send.click();

  api.syncSendTrackerFromDOM();
  const entry = api.getSendTrackerEntry();
  assert.ok(entry, 'Accepted first send in true new conversation must be recorded');
  assert.strictEqual(entry.provenance, 'observed');
  assert.ok(entry.timestamp > 0);
});

test('W7-016 30: Mouse and keyboard Send acceptance', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  h.sandbox.location.pathname = '/c/interactive-chat';

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);

  // Initial sync with 1 turn so conversation is hydrated
  const baseTurn = userTurn(h, 'base-turn-1', 'Initial prompt');
  addTurns(h, [baseTurn]);
  api.syncSendTrackerFromDOM();

  // 1. Mouse click acceptance
  fixture.input.textContent = 'Click message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  const entryMouse = api.getSendTrackerEntry('c:interactive-chat');
  assert.ok(entryMouse, 'Mouse click send must be recorded');
  const mouseTime = entryMouse.timestamp;

  h.advance(2000);

  // 2. Keyboard Enter acceptance
  fixture.input.textContent = 'Enter message';
  fixture.input.dispatchEvent(new FakeEvent('keydown', { key: 'Enter', code: 'Enter' }));
  const keyTurn = userTurn(h, 'key-turn-2', 'Enter message');
  addTurns(h, [keyTurn]);
  fixture.input.textContent = '';
  api.syncSendTrackerFromDOM();

  const entryKey = api.getSendTrackerEntry('c:interactive-chat');
  assert.ok(entryKey);
  assert.ok(entryKey.timestamp >= mouseTime);
});

test('W7-016 31: Rejected Send preserves timestamp', async () => {
  const { h, api } = setup();
  const currentKey = api.currentConversationKey();
  const originalTime = Date.now() - 600000; // 10 min ago

  api.setSendTrackerEntry(currentKey, {
    timestamp: originalTime,
    turnId: 'turn-good-1',
    provenance: 'observed'
  });

  const fixture = composerFixture(h);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Failed message';
  fixture.send.click();

  // Send failed - no turn added, input not consumed
  api.syncSendTrackerFromDOM();
  const entry = api.getSendTrackerEntry(currentKey);
  assert.strictEqual(entry.timestamp, originalTime, 'Rejected send attempt must not modify send timestamp');
});

test('W7-016 32: Reload with old history and persisted timestamp', async () => {
  const { h, api } = setup();
  const currentKey = 'c:persisted-chat-reload';
  h.sandbox.location.pathname = '/c/persisted-chat-reload';
  const persistedTime = Date.now() - 7200000; // 2 hours ago

  api.setSendTrackerEntry(currentKey, {
    timestamp: persistedTime,
    turnId: 'turn-persisted',
    provenance: 'authoritative'
  });

  // Empty DOM initially on reload
  api.syncSendTrackerFromDOM();
  let entry = api.getSendTrackerEntry(currentKey);
  assert.strictEqual(entry.timestamp, persistedTime);

  // History loads in DOM
  const turn = userTurn(h, 'turn-persisted', 'Old query');
  addTurns(h, [turn]);
  api.syncSendTrackerFromDOM();

  entry = api.getSendTrackerEntry(currentKey);
  assert.strictEqual(entry.timestamp, persistedTime, 'Persisted timestamp must not be overwritten by hydration');
  assert.strictEqual(entry.provenance, 'authoritative');
});

test('W7-016 33: Rapid navigation across conversations', async () => {
  const { h, api } = setup();
  const now = Date.now();
  const tA = now - 50000;
  const tB = now - 100000;
  const tC = now - 150000;

  api.setSendTrackerEntry('c:chat-nav-a', { timestamp: tA, turnId: 'a', provenance: 'authoritative' });
  api.setSendTrackerEntry('c:chat-nav-b', { timestamp: tB, turnId: 'b', provenance: 'authoritative' });
  api.setSendTrackerEntry('c:chat-nav-c', { timestamp: tC, turnId: 'c', provenance: 'authoritative' });

  for (let i = 0; i < 5; i++) {
    h.sandbox.location.pathname = '/c/chat-nav-a';
    assert.strictEqual(api.getSendTrackerEntry()?.timestamp, tA);
    h.sandbox.location.pathname = '/c/chat-nav-b';
    assert.strictEqual(api.getSendTrackerEntry()?.timestamp, tB);
    h.sandbox.location.pathname = '/c/chat-nav-c';
    assert.strictEqual(api.getSendTrackerEntry()?.timestamp, tC);
  }
});

test('W7-016 34: Out-of-order hydration and route transitions', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  h.sandbox.location.pathname = '/'; // draft chat

  // First turn sent in draft
  const draftKey = api.currentConversationKey();
  const now = Date.now();
  api.setSendTrackerEntry(draftKey, { timestamp: now, turnId: 'draft-t1', provenance: 'observed' });

  // Conversation transitions from draft to stable route c:new-chat-999
  const stableKey = 'c:new-chat-999';
  api.migrateSendTracker(draftKey, stableKey);
  h.sandbox.location.pathname = '/c/new-chat-999';

  const entry = api.getSendTrackerEntry(stableKey);
  assert.ok(entry);
  assert.strictEqual(entry.timestamp, now);
  assert.strictEqual(entry.turnId, 'draft-t1');
});

test('W7-016 35: Cached archive replaced on Bridge', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const oldTs = Date.parse('2026-10-08T05:14:51');
  const newTs = Date.parse('2026-10-08T23:08:10');

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip',
    timestamp: oldTs,
    source: 'archive filename',
    mtime: Math.floor(oldTs / 1000)
  });

  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  await h.settle();
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 05:14:51');

  // Bridge now offers a new archive
  h.httpResponder = options => {
    if (String(options?.url || '').includes('/archive/metadata')) {
      return {
        status: 200,
        responseText: JSON.stringify({
          ok: true,
          project_id: 'audapack',
          filename: '_AUDAPACK_08.10.26-T23-08-10.zip',
          mtime: Math.floor(newTs / 1000)
        })
      };
    }
    return { status: 404 };
  };

  // Trigger metadata refresh
  const pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 23:08:10', 'Canonical ZIP clock must refresh when Bridge offers newer archive');
});

test('W7-016 36: Metadata response arrives after project switch', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const tsA = Date.parse('2026-10-08T05:14:51');
  const tsB = Date.parse('2026-10-08T08:30:00');

  api.setVerifiedProjectArchive('proj-a', {
    filename: '_PROJA_08.10.26-T05-14-51.zip',
    timestamp: tsA,
    source: 'archive filename'
  });
  api.setVerifiedProjectArchive('proj-b', {
    filename: '_PROJB_08.10.26-T08-30-00.zip',
    timestamp: tsB,
    source: 'archive filename'
  });

  // Bound to proj-b
  api.setManualArchiveBinding({ project_id: 'proj-b', display_name: 'Project B' });

  // Simulate stale response for proj-a resolving now
  h.httpResponder = options => {
    return {
      status: 200,
      responseText: JSON.stringify({
        ok: true,
        project_id: 'proj-a',
        filename: '_PROJA_08.10.26-T12-00-00.zip',
        mtime: 1728388800
      })
    };
  };

  const pending = api.refreshProjectArchiveMetadata('proj-a');
  await h.settle();
  await pending;

  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  // Indicator must show proj-b, not contaminated by proj-a!
  assert.strictEqual(zipEl.textContent, 'ZIP 08:30:00');
  assert.ok(zipEl.title.includes('Project: Project B'));
});

test('W7-016 37: Offline Bridge while cached time exists', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const ts = Date.parse('2026-10-08T05:14:51');
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip',
    timestamp: ts,
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });

  // Bridge is offline
  h.httpResponder = () => { throw new Error('Failed to connect to Bridge: ECONNREFUSED'); };

  const pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;

  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 05:14:51', 'Cached time must survive Bridge outage');
});

test('W7-016 38: Reconnect and bounded refresh', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const newTs = Date.parse('2026-10-08T18:00:00');
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  await h.settle();

  // Bridge reconnects
  h.httpResponder = options => ({
    status: 200,
    responseText: JSON.stringify({
      ok: true,
      project_id: 'audapack',
      filename: '_AUDAPACK_08.10.26-T18-00-00.zip',
      mtime: Math.floor(newTs / 1000)
    })
  });

  const pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 18:00:00');
});

test('W7-016 39: Attached versus canonical archive precedence', async () => {
  const { h, api } = setup();
  const fixture = composerFixture(h);
  api.clearVerifiedProjectArchives();

  const canonicalTs = Date.parse('2026-10-08T10:00:00');
  const attachedTs = Date.parse('2026-10-08T14:00:00');

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T10-00-00.zip',
    timestamp: canonicalTs,
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });

  // 1. Initially no attachment: shows canonical
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 10:00:00');

  // 2. Attach newer archive into composer: canonical authority wins, the
  // attachment stays separately identifiable and never persists (T-298).
  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T14-00-00.zip');
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 10:00:00');
  assert.ok(zipEl.title.includes('Attached: _AUDAPACK_08.10.26-T14-00-00.zip'));
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_08.10.26-T10-00-00.zip');

  // 3. Detach: canonical verified archive remains
  tile.remove();
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 10:00:00', 'Canonical timestamp retained after detach');
});

test('W7-016 40: Browser file mtime versus Bridge mtime', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();

  // 1. Browser file mtime (from File object without parsed filename timestamp)
  const browserMtime = Date.parse('2026-10-08T09:15:00');
  api.setVerifiedProjectArchive('proj-browser', {
    filename: 'custom_archive.zip',
    timestamp: browserMtime,
    source: 'browser file mtime'
  });
  api.setManualArchiveBinding({ project_id: 'proj-browser', display_name: 'BrowserProj' });
  api.renderTitlebarIndicators();

  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.ok(zipEl.title.includes('Source: browser file mtime'), 'Must show browser file mtime');
  assert.ok(zipEl.title.includes('Last modified:'), 'Must show Last modified label');
  assert.ok(!zipEl.title.includes('Source: bridge mtime'), 'Must NOT mislabel as bridge mtime');

  // 2. Bridge mtime
  const bridgeMtime = Date.parse('2026-10-08T11:20:00');
  api.setVerifiedProjectArchive('proj-bridge', {
    filename: 'repo_backup.zip',
    timestamp: bridgeMtime,
    source: 'bridge mtime',
    mtime: Math.floor(bridgeMtime / 1000)
  });
  api.setManualArchiveBinding({ project_id: 'proj-bridge', display_name: 'BridgeProj' });
  api.renderTitlebarIndicators();

  assert.ok(zipEl.title.includes('Source: bridge mtime'), 'Must show bridge mtime');
  assert.ok(zipEl.title.includes('Last modified:'), 'Must show Last modified label');
});

test('W7-016 41: Invalid or missing metadata', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();

  // Null/empty metadata
  api.setVerifiedProjectArchive('proj-empty', null);
  api.setManualArchiveBinding({ project_id: 'proj-empty', display_name: 'EmptyProj' });
  api.renderTitlebarIndicators();

  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP —');
  assert.ok(zipEl.title.includes('No archive timestamp available'));
});

test('W7-016 42: Timer activity after repeated mounts', async () => {
  const { h, api } = setup();

  const baseTimers = h.timers.pending().length;
  for (let i = 0; i < 5; i++) {
    api.mount();
    api.startSendAgeTimer();
  }

  assert.strictEqual(api.isSendAgeTimerActive, true);
  // Verify only one timer is running for send age ticker
  assert.strictEqual(h.timers.pending().length, baseTimers + 1);
  api.cancelSendAgeTimer();
  assert.strictEqual(api.isSendAgeTimerActive, false);
  assert.strictEqual(h.timers.pending().length, baseTimers);
});

test('W7-016 43: Background pause and foreground catch-up', async () => {
  const { h, api } = setup();
  const currentKey = api.currentConversationKey();
  const sendTime = Date.now() - 10000; // 10s ago

  api.setSendTrackerEntry(currentKey, {
    timestamp: sendTime,
    turnId: 'turn-bg',
    provenance: 'observed'
  });

  api.startSendAgeTimer();
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  api.renderTitlebarIndicators(sendTime + 10000);
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:00:10');

  // Go to background
  h.sandbox.document.hidden = true;
  h.sandbox.document.dispatchEvent(new FakeEvent('visibilitychange'));
  assert.strictEqual(api.isSendAgeTimerActive, false, 'Timer must pause in background');

  // Fast forward 50 seconds in background
  h.advance(50000);

  // Return to foreground
  h.sandbox.document.hidden = false;
  h.sandbox.document.dispatchEvent(new FakeEvent('visibilitychange'));
  assert.strictEqual(api.isSendAgeTimerActive, true, 'Timer must resume on foreground');

  // Upon return, indicator must catch up to elapsed time (10s + 50s = 60s)
  api.renderTitlebarIndicators(sendTime + 60000);
  assert.strictEqual(sendAgeEl.textContent, 'SEND 00:01:00');
  api.cancelSendAgeTimer();
});

test('W7-016 44: No extra per-second archive inventory traversal', async () => {
  const { h, api } = setup();
  const fixture = composerFixture(h);
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');

  h.timers.flush();
  api.startSendAgeTimer();
  api.renderTitlebarIndicators();
  const initialQsa = h.counters.qsa;

  // Run 5 second ticks
  for (let i = 0; i < 5; i++) {
    h.advance(1000);
  }

  const qsaDelta = h.counters.qsa - initialQsa;
  // Per-second tick should not perform full composer attachment traversal (which before fix was ~700 qsa)
  assert.ok(qsaDelta < 200, `Expected minimal DOM queries over 5 ticks, got ${qsaDelta}`);
  api.cancelSendAgeTimer();
});

test('W7-016 45: Stable idle DOM-query and storage-read counts', async () => {
  const { h, api } = setup();
  h.timers.flush();
  api.renderTitlebarIndicators();

  const startGmGet = h.counters.gmGet;

  // Run 10 ticks in idle state
  for (let i = 0; i < 10; i++) {
    h.advance(1000);
  }

  const gmGetDelta = h.counters.gmGet - startGmGet;
  // Persistent storage should be cached in memory, not deserialized 10 times
  assert.ok(gmGetDelta <= 2, `Expected <= 2 GM_getValue reads across 10 idle ticks, got ${gmGetDelta}`);
});

// ---------------------------------------------------------------------------
// T-296 corrective coverage: opaque UUID fixtures, controlled wall-clock +
// fake timers, document-level delegated Send tracking, autonomous ZIP polling.
// ---------------------------------------------------------------------------

function stubWallClock(h, startMs) {
  let fakeNow = startMs;
  h.sandbox.Date.now = () => fakeNow;
  return {
    now: () => fakeNow,
    advance: ms => { fakeNow += ms; h.advance(ms); }
  };
}

function bridgeMetadataResponder(h, state) {
  h.httpResponder = options => {
    if (String(options?.url || '').includes('/archive/metadata')) {
      state.requests += 1;
      if (state.fail) throw new Error('Failed to connect to Bridge: ECONNREFUSED');
      return {
        status: 200,
        responseText: JSON.stringify({
          ok: true,
          project_id: state.projectId,
          filename: state.filename,
          mtime: Math.floor(state.mtime / 1000)
        })
      };
    }
    return { status: 404 };
  };
}

test('W7-016 46: Stable UUID chat, empty DOM, delayed old history (Failure A)', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:44aaff22-bbcc-4455-9900-aa1122334455';
  h.sandbox.location.pathname = '/c/44aaff22-bbcc-4455-9900-aa1122334455';

  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null);

  const oldTurn = userTurn(h, '914a0fd4-d125-4f7e-ab2a-987654321012', 'Historical message');
  addTurns(h, [oldTurn]);
  api.syncSendTrackerFromDOM();

  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'no Send fabricated from late history');
  const sendAgeEl = h.dom.querySelector('#acb-send-age');
  api.renderTitlebarIndicators();
  assert.strictEqual(sendAgeEl.textContent, 'SEND —');
});

test('W7-016 47: Multiple old turns arriving asynchronously fabricate nothing', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:0a1b2c3d-1111-4222-8333-aaaaaaaaaaaa';
  h.sandbox.location.pathname = '/c/0a1b2c3d-1111-4222-8333-aaaaaaaaaaaa';

  api.syncSendTrackerFromDOM();
  const chunks = [
    '1b2c3d4e-2222-4222-8333-bbbbbbbbbbbb',
    '2c3d4e5f-3333-4222-8333-cccccccccccc',
    '3d4e5f6a-4444-4222-8333-dddddddddddd'
  ];
  for (const id of chunks) {
    addTurns(h, [userTurn(h, id, `History chunk ${id}`)]);
    h.advance(1500);
    api.syncSendTrackerFromDOM();
    assert.strictEqual(api.getSendTrackerEntry(convo), null, `chunk ${id} must not fabricate a Send`);
  }
});

test('W7-016 48: Persisted authoritative Send survives a different old turn (Failure B)', async () => {
  const { h, api } = setup();
  const convo = 'c:77aa1122-cc33-44dd-55ee-ff0011223344';
  h.sandbox.location.pathname = '/c/77aa1122-cc33-44dd-55ee-ff0011223344';
  const persistedTime = Date.now() - 7200000;

  api.setSendTrackerEntry(convo, {
    timestamp: persistedTime,
    turnId: 'a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5',
    provenance: 'authoritative'
  });

  api.syncSendTrackerFromDOM();
  const oldTurn = userTurn(h, 'f9e8d7c6-b5a4-4938-8271-001122334455', 'Old turn, different UUID');
  addTurns(h, [oldTurn]);
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.strictEqual(entry.timestamp, persistedTime, 'original persisted timestamp intact');
  assert.strictEqual(entry.provenance, 'authoritative');
  assert.strictEqual(entry.turnId, 'a1b2c3d4-e5f6-4a7b-8c9d-e0f1a2b3c4d5');
});

test('W7-016 49: Reload with partially hydrated UUID history preserves timestamp', async () => {
  const { h, api } = setup();
  const convo = 'c:9a8b7c6d-5555-4222-8333-eeeeeeeeeeee';
  h.sandbox.location.pathname = '/c/9a8b7c6d-5555-4222-8333-eeeeeeeeeeee';
  const persistedTime = Date.now() - 5400000;

  api.setSendTrackerEntry(convo, {
    timestamp: persistedTime,
    turnId: 'deadbeef-aaaa-4bbb-8ccc-feedfeedfeed',
    provenance: 'authoritative'
  });

  // Reload: empty DOM, then only the OLDER part of history hydrates.
  api.syncSendTrackerFromDOM();
  addTurns(h, [userTurn(h, 'cafe0001-1111-4222-8333-111111111111', 'Older turn')]);
  api.syncSendTrackerFromDOM();
  let entry = api.getSendTrackerEntry(convo);
  assert.strictEqual(entry.timestamp, persistedTime);
  assert.strictEqual(entry.provenance, 'authoritative');

  // The recorded Send turn itself hydrates: still preserved, steady state.
  addTurns(h, [userTurn(h, 'deadbeef-aaaa-4bbb-8ccc-feedfeedfeed', 'The send turn')]);
  api.syncSendTrackerFromDOM();
  entry = api.getSendTrackerEntry(convo);
  assert.strictEqual(entry.timestamp, persistedTime);
  assert.strictEqual(entry.provenance, 'authoritative');
});

test('W7-016 50: Stable chat first accepted Send after hydration', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:13572468-6666-4222-8333-ffffffffffff';
  h.sandbox.location.pathname = '/c/13572468-6666-4222-8333-ffffffffffff';

  // History hydrates first: nothing recorded.
  api.syncSendTrackerFromDOM();
  addTurns(h, [userTurn(h, 'abcd0001-7777-4222-8333-222222222222', 'Old history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null);

  // Operator sends: intent + accepted turn/composer transition.
  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.input.textContent = 'Fresh question after hydration';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.ok(entry, 'accepted Send after hydration recorded');
  assert.strictEqual(entry.provenance, 'observed');
  assert.ok(entry.timestamp > 0);
});

test('W7-016 51: Click without accepted submission records nothing', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:24681357-8888-4222-8333-333333333333';
  h.sandbox.location.pathname = '/c/24681357-8888-4222-8333-333333333333';

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true; // ChatGPT refuses: composer untouched, no turn

  fixture.input.textContent = 'Message that never sends';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'failed click records nothing');

  // Late history racing the failed click still records nothing: the composer
  // still holds the authored payload, so no acceptance transition exists.
  addTurns(h, [userTurn(h, 'beef0002-9999-4222-8333-444444444444', 'Late history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null);

  // A prior timestamp is equally preserved by the failed click.
  const prior = Date.now() - 600000;
  api.setSendTrackerEntry(convo, { timestamp: prior, turnId: 'aa00aa00-0000-4222-8333-555555555555', provenance: 'observed' });
  fixture.input.textContent = 'Another failed message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo).timestamp, prior);
});

test('W7-016 52: Entry without turn id binds history without moving the clock', async () => {
  const { h, api } = setup();
  const convo = 'c:11223344-aaaa-4222-8333-666666666666';
  h.sandbox.location.pathname = '/c/11223344-aaaa-4222-8333-666666666666';
  const sendTime = Date.now() - 900000;

  // Widget-verified automatic Send recorded before its turn hydrated.
  api.recordSendObservation(convo, { timestamp: sendTime, provenance: 'widget-send' });
  assert.strictEqual(api.getSendTrackerEntry(convo).turnId, '');

  const turn = userTurn(h, 'cc11cc11-bbbb-4ccc-8ddd-777777777777', 'History turn');
  addTurns(h, [turn]);
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.strictEqual(entry.timestamp, sendTime, 'timestamp untouched by hydration');
  assert.strictEqual(entry.provenance, 'widget-send');
  assert.strictEqual(entry.turnId, 'cc11cc11-bbbb-4ccc-8ddd-777777777777');
});

function stubWallClockTick(h, ms) {
  const current = h.sandbox.Date.now;
  const next = current() + ms;
  h.sandbox.Date.now = () => next;
  h.advance(ms);
}

test('W7-016 53: Hydration on one stable chat never leaks into another', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convoA = 'c:aaaa0001-aaaa-4222-8333-888888888888';
  const convoB = 'c:bbbb0002-bbbb-4222-8333-999999999999';

  h.sandbox.location.pathname = '/c/aaaa0001-aaaa-4222-8333-888888888888';
  api.syncSendTrackerFromDOM();
  addTurns(h, [userTurn(h, 'a1a1a1a1-cccc-4222-8333-101010101010', 'Chat A history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convoA), null);

  // Route transition mid-hydration: chat B hydrates its own history.
  h.sandbox.location.pathname = '/c/bbbb0002-bbbb-4222-8333-999999999999';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  api.syncSendTrackerFromDOM();
  addTurns(h, [userTurn(h, 'b2b2b2b2-dddd-4222-8333-202020202020', 'Chat B history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convoB), null);
  assert.strictEqual(api.getSendTrackerEntry(convoA), null);

  // Accepted Send in B stays in B.
  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.input.textContent = 'Chat B question';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.ok(api.getSendTrackerEntry(convoB), 'chat B Send recorded');
  assert.strictEqual(api.getSendTrackerEntry(convoA), null, 'chat A untouched');
});

test('W7-016 54: Two tabs sharing one conversation stay consistent', async () => {
  const { h, api } = setup();
  const convo = 'c:cccccccc-cccc-4222-8333-303030303030';
  h.sandbox.location.pathname = '/c/cccccccc-cccc-4222-8333-303030303030';

  // Tab 1: operator sends; entry persisted to shared GM storage.
  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.input.textContent = 'Tab 1 question';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  const entry1 = api.getSendTrackerEntry(convo);
  assert.ok(entry1);

  // Tab 2: independent harness, same shared GM bytes, own memory baseline.
  const { createHarness } = require('./harness');
  const h2raw = createHarness();
  for (const [key, value] of h.gmStore) h2raw.gmStore.set(key, value);
  const api2 = h2raw.load();
  h2raw.sandbox.location.pathname = '/c/cccccccc-cccc-4222-8333-303030303030';

  // Tab 2 sees only old history with a different turn id: must preserve.
  const { userTurn: userTurn2, addTurns: addTurns2 } = require('./helpers');
  addTurns2(h2raw, [userTurn2(h2raw, 'd4d4d4d4-eeee-4222-8333-404040404040', 'Old history in tab 2')]);
  api2.syncSendTrackerFromDOM();
  const entry2 = api2.getSendTrackerEntry(convo);
  assert.strictEqual(entry2.timestamp, entry1.timestamp, 'tab 2 preserves tab 1 timestamp');
  assert.strictEqual(entry2.provenance, entry1.provenance);
});

test('W7-016 55: Canonical archive replacement lands during idle', async () => {
  const { h, api } = setup();
  const clock = stubWallClock(h, Date.now());
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const oldTs = Date.parse('2026-10-08T05:14:51');
  const newTs = Date.parse('2026-10-08T23:08:10');
  const state = {
    requests: 0, fail: false, projectId: 'audapack',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', mtime: oldTs
  };
  bridgeMetadataResponder(h, state);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', timestamp: oldTs, source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  api.renderTitlebarIndicators();
  api.startSendAgeTimer();
  api.startArchiveMetadataPoll();
  await h.settle();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 05:14:51');

  // Bridge publishes a newer canonical archive mid-idle; no UI interaction.
  state.filename = '_AUDAPACK_08.10.26-T23-08-10.zip';
  state.mtime = newTs;
  for (let i = 0; i < 35; i += 1) clock.advance(1000);
  await h.settle();

  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 23:08:10', 'idle poller picks up canonical replacement');
  assert.ok(state.requests >= 1 && state.requests <= 4, `bounded requests, got ${state.requests}`);
  api.cancelSendAgeTimer();
  api.cancelArchiveMetadataPoll();
});

test('W7-016 56: No metadata request storm while idle', async () => {
  const { h, api } = setup();
  stubWallClock(h, Date.now());
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const oldTs = Date.parse('2026-10-08T05:14:51');
  const state = {
    requests: 0, fail: false, projectId: 'audapack',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', mtime: oldTs
  };
  bridgeMetadataResponder(h, state);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', timestamp: oldTs, source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  api.renderTitlebarIndicators();
  api.startSendAgeTimer();
  api.startArchiveMetadataPoll();
  await h.settle();

  for (let i = 0; i < 70; i += 1) stubWallClockTick(h, 1000);
  await h.settle();

  assert.ok(state.requests >= 2, `scheduler alive, got ${state.requests}`);
  assert.ok(state.requests <= 5, `no storm over 70s idle, got ${state.requests}`);
  api.cancelSendAgeTimer();
  api.cancelArchiveMetadataPoll();
});

test('W7-016 57: Bridge failure preserves cache, recovery refreshes via poller', async () => {
  const { h, api } = setup();
  stubWallClock(h, Date.now());
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const oldTs = Date.parse('2026-10-08T05:14:51');
  const newTs = Date.parse('2026-10-08T18:00:00');
  const state = {
    requests: 0, fail: true, projectId: 'audapack',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', mtime: oldTs
  };
  bridgeMetadataResponder(h, state);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', timestamp: oldTs, source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  api.renderTitlebarIndicators();
  api.startArchiveMetadataPoll();
  await h.settle();

  // 45 s offline idle: attempts stay bounded, cached display survives.
  const t0 = h.sandbox.Date.now();
  for (let i = 0; i < 45; i += 1) stubWallClockTick(h, 1000);
  await h.settle();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  api.renderTitlebarIndicators(h.sandbox.Date.now());
  assert.strictEqual(zipEl.textContent, 'ZIP 05:14:51', 'cached time survives outage');
  assert.ok(state.requests <= 4, `backoff bounds offline attempts, got ${state.requests}`);

  // Bridge recovers with a newer archive: poller refreshes without interaction.
  state.fail = false;
  state.filename = '_AUDAPACK_08.10.26-T18-00-00.zip';
  state.mtime = newTs;
  for (let i = 0; i < 45; i += 1) stubWallClockTick(h, 1000);
  await h.settle();
  api.renderTitlebarIndicators(h.sandbox.Date.now());
  assert.strictEqual(zipEl.textContent, 'ZIP 18:00:00', 'recovery refreshes display');
  assert.ok(h.sandbox.Date.now() - t0 >= 90000);
  api.cancelArchiveMetadataPoll();
});

test('W7-016 58: Hidden tab suppresses polling, foreground catches up', async () => {
  const { h, api } = setup();
  stubWallClock(h, Date.now());
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const oldTs = Date.parse('2026-10-08T05:14:51');
  const state = {
    requests: 0, fail: false, projectId: 'audapack',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', mtime: oldTs
  };
  bridgeMetadataResponder(h, state);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', timestamp: oldTs, source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  api.renderTitlebarIndicators();
  api.startSendAgeTimer();
  api.startArchiveMetadataPoll();
  await h.settle();
  state.requests = 0;

  // Hidden for 60 s: no metadata requests.
  h.sandbox.document.hidden = true;
  h.sandbox.document.dispatchEvent(new FakeEvent('visibilitychange'));
  assert.strictEqual(api.isSendAgeTimerActive, false);
  assert.strictEqual(api.isArchiveMetadataPollActive, false, 'poller paused while hidden');
  for (let i = 0; i < 60; i += 1) stubWallClockTick(h, 1000);
  await h.settle();
  assert.strictEqual(state.requests, 0, 'no polling while hidden');

  // Foreground: poller restarts and catches up with one bounded validation.
  h.sandbox.document.hidden = false;
  h.sandbox.document.dispatchEvent(new FakeEvent('visibilitychange'));
  assert.strictEqual(api.isArchiveMetadataPollActive, true, 'poller resumes on foreground');
  await h.settle();
  assert.ok(state.requests >= 1, 'foreground catch-up validates metadata');
  assert.ok(state.requests <= 2, `catch-up bounded, got ${state.requests}`);
  api.cancelSendAgeTimer();
  api.cancelArchiveMetadataPoll();
});

test('W7-016 59: Repeated mount/teardown leaves exactly one scheduler each', async () => {
  const { h, api } = setup();

  const baseTimers = h.timers.pending().length;
  for (let i = 0; i < 5; i += 1) {
    api.mount();
    api.startSendAgeTimer();
    api.startArchiveMetadataPoll();
  }

  assert.strictEqual(api.isSendAgeTimerActive, true);
  assert.strictEqual(api.isArchiveMetadataPollActive, true);
  assert.strictEqual(h.timers.pending().length, baseTimers + 2, 'one send timer + one metadata timer');

  // Teardown cancels both; remount restarts exactly one each.
  api.cancelSendAgeTimer();
  api.cancelArchiveMetadataPoll();
  assert.strictEqual(h.timers.pending().length, baseTimers);
  api.mount();
  api.startSendAgeTimer();
  api.startArchiveMetadataPoll();
  assert.strictEqual(h.timers.pending().length, baseTimers + 2);
  api.cancelSendAgeTimer();
  api.cancelArchiveMetadataPoll();
});

test('W7-016 60: Per-second ticks issue no metadata scans', async () => {
  const { h, api } = setup();
  stubWallClock(h, Date.now());
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const oldTs = Date.parse('2026-10-08T05:14:51');
  const state = {
    requests: 0, fail: false, projectId: 'audapack',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', mtime: oldTs
  };
  bridgeMetadataResponder(h, state);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', timestamp: oldTs, source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  api.renderTitlebarIndicators();
  api.startSendAgeTimer();
  api.startArchiveMetadataPoll();
  await h.settle();
  state.requests = 0;

  const startQsa = h.counters.qsa;
  for (let i = 0; i < 10; i += 1) stubWallClockTick(h, 1000);
  await h.settle();

  assert.strictEqual(state.requests, 0, 'no metadata polling inside a 10 s window');
  const qsaDelta = h.counters.qsa - startQsa;
  assert.ok(qsaDelta < 200, `minimal DOM queries over 10 ticks, got ${qsaDelta}`);
  api.cancelSendAgeTimer();
  api.cancelArchiveMetadataPoll();
});

test('W7-016 61: Idle polling performs no persistent writes', async () => {
  const { h, api } = setup();
  stubWallClock(h, Date.now());
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();

  const oldTs = Date.parse('2026-10-08T05:14:51');
  const state = {
    requests: 0, fail: false, projectId: 'audapack',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', mtime: oldTs
  };
  bridgeMetadataResponder(h, state);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip', timestamp: oldTs, source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  api.renderTitlebarIndicators();
  api.startSendAgeTimer();
  api.startArchiveMetadataPoll();
  await h.settle();

  const startGmSet = h.counters.gmSet;
  // 40 s idle with unchanged canonical data: polls validate, nothing rewrites.
  for (let i = 0; i < 40; i += 1) stubWallClockTick(h, 1000);
  await h.settle();

  assert.ok(state.requests >= 1, `poller validated, got ${state.requests}`);
  assert.strictEqual(h.counters.gmSet - startGmSet, 0, 'equal metadata must not rewrite storage');
  api.cancelSendAgeTimer();
  api.cancelArchiveMetadataPoll();
});
// ---------------------------------------------------------------------------
// P1-A / P1-B corrective coverage: stale composer attachment must not
// downgrade verified canonical metadata; failed Sends must never fabricate.
// Opaque UUID fixtures, controlled wall-clock + fake timers, document-level
// delegated Send tracking.
// ---------------------------------------------------------------------------

test('W7-016 62 (A1): Newer canonical metadata plus older composer archive', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  composerFixture(h);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });

  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 03:31:16', 'ZIP shows newer canonical, not stale attachment');
  assert.ok(zipEl.title.includes('Attached: _AUDAPACK_08.10.26-T05-14-51.zip'), 'attachment stays separately identifiable');
  const stored = api.getVerifiedProjectArchive('audapack');
  assert.strictEqual(stored.filename, '_AUDAPACK_09.10.26-T03-31-16.zip', 'canonical store survives stale attachment');
});

test('W7-016 63 (A2): Repeated renders with unchanged composer attachment', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  composerFixture(h);
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  api.renderTitlebarIndicators();

  const startSets = h.counters.gmSet;
  for (let i = 0; i < 10; i += 1) api.renderTitlebarIndicators();
  assert.strictEqual(h.counters.gmSet - startSets, 0, '10 unchanged renders perform zero persistent writes');
});

test('W7-016 64 (A3): Detach older attachment after observing newer canonical data', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  composerFixture(h);
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });

  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 03:31:16');

  tile.remove();
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 03:31:16', 'detaching stale attachment never destroys canonical metadata');
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T03-31-16.zip');
});

test('W7-016 65 (A4): Bridge refresh while older attachment remains attached', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();
  composerFixture(h);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  await h.settle();
  api.renderTitlebarIndicators();
  assert.strictEqual(h.dom.querySelector('#acb-archive-timestamp').textContent, 'ZIP 03:31:16');

  const state = { requests: 0, fail: false, projectId: 'audapack', filename: '_AUDAPACK_09.10.26-T04-45-00.zip', mtime: Date.parse('2026-10-09T04:45:00') };
  bridgeMetadataResponder(h, state);
  const pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;

  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 04:45:00', 'Bridge canonical wins over stale attachment');
  api.renderTitlebarIndicators();
  assert.strictEqual(zipEl.textContent, 'ZIP 04:45:00', 'Bridge update survives re-render with old attachment present');
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T04-45-00.zip');
});

test('W7-016 66 (A5): Canonical archive genuinely replaced by older timestamp', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();
  composerFixture(h);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T04-45-00.zip',
    timestamp: Date.parse('2026-10-09T04:45:00'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  await h.settle();
  api.renderTitlebarIndicators();
  assert.strictEqual(h.dom.querySelector('#acb-archive-timestamp').textContent, 'ZIP 04:45:00');

  // Bridge explicitly confirms the current canonical identity is an older
  // archive (legitimate rollback/replacement): identity change is accepted.
  const state = { requests: 0, fail: false, projectId: 'audapack', filename: '_AUDAPACK_07.10.26-T22-05-40.zip', mtime: Date.parse('2026-10-07T22:05:40') };
  bridgeMetadataResponder(h, state);
  const pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;

  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 22:05:40', 'Bridge-confirmed replacement accepted despite older timestamp');
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_07.10.26-T22-05-40.zip');
});

test('W7-016 67 (A6): Different project archive attached to bound conversation', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  composerFixture(h);
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });

  addComposerAttachmentTile(h, '_FASTPROMPTER_08.10.26-T08-30-00.zip');
  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP —', 'foreign-project attachment never displays as bound metadata');
  assert.strictEqual(api.getVerifiedProjectArchive('audapack'), null, 'foreign attachment never persists over bound project');
});

test('W7-016 68 (A7): Delayed response from previously bound project', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();
  composerFixture(h);

  api.setVerifiedProjectArchive('proj-a', {
    filename: '_PROJA_08.10.26-T05-14-51.zip', timestamp: Date.parse('2026-10-08T05:14:51'), source: 'archive filename'
  });
  api.setVerifiedProjectArchive('proj-b', {
    filename: '_PROJB_08.10.26-T08-30-00.zip', timestamp: Date.parse('2026-10-08T08:30:00'), source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'proj-b', display_name: 'Project B' });

  // A late Bridge response for the previously bound project resolves now.
  h.httpResponder = () => ({
    status: 200,
    responseText: JSON.stringify({
      ok: true, project_id: 'proj-a',
      filename: '_PROJA_08.10.26-T12-00-00.zip', mtime: Math.floor(Date.parse('2026-10-08T12:00:00') / 1000)
    })
  });
  const pending = api.refreshProjectArchiveMetadata('proj-a');
  await h.settle();
  await pending;

  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 08:30:00', 'bound display unaffected by foreign response');
  assert.ok(zipEl.title.includes('Project: Project B'));
  assert.strictEqual(api.getVerifiedProjectArchive('proj-a').filename, '_PROJA_08.10.26-T12-00-00.zip', 'per-project store still updates in isolation');
});

test('W7-016 69 (A8): Same filename and timestamp cause zero additional writes', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  composerFixture(h);
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  addComposerAttachmentTile(h, '_AUDAPACK_09.10.26-T03-31-16.zip');
  api.renderTitlebarIndicators();

  const startSets = h.counters.gmSet;
  for (let i = 0; i < 10; i += 1) api.renderTitlebarIndicators();
  assert.strictEqual(h.counters.gmSet - startSets, 0, 'identical metadata across 10 renders writes nothing');
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 03:31:16');
});

test('W7-016 70 (A9): Archive replacement produces only necessary writes', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();
  composerFixture(h);
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  await h.settle();
  api.renderTitlebarIndicators();

  const state = { requests: 0, fail: false, projectId: 'audapack', filename: '_AUDAPACK_09.10.26-T04-45-00.zip', mtime: Date.parse('2026-10-09T04:45:00') };
  bridgeMetadataResponder(h, state);

  const startSets = h.counters.gmSet;
  let pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;
  assert.strictEqual(h.counters.gmSet - startSets, 1, 'one replacement writes exactly once');

  for (let i = 0; i < 3; i += 1) {
    pending = api.refreshProjectArchiveMetadata('audapack');
    await h.settle();
    await pending;
  }
  assert.strictEqual(h.counters.gmSet - startSets, 1, 'identical follow-up refreshes write nothing more');
});

test('W7-016 71 (A10): Offline Bridge preserves latest verified metadata', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();
  composerFixture(h);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');

  h.httpResponder = () => { throw new Error('Failed to connect to Bridge: ECONNREFUSED'); };
  const pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;

  api.renderTitlebarIndicators();
  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 03:31:16', 'cached canonical survives outage despite stale attachment');
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T03-31-16.zip');
});

test('W7-016 72 (B1): Failed Send, unchanged draft, late historical turn', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:b1000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b1000000-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'b1111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Original unsent message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'failed Send records nothing');
  assert.strictEqual(String(fixture.input.textContent), 'Original unsent message', 'draft remains intact');

  addTurns(h, [userTurn(h, 'b1222222-2222-4222-8333-333333333333', 'Late historical turn')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'unchanged draft + late history fabricates nothing');
  assert.strictEqual(String(fixture.input.textContent), 'Original unsent message', 'draft still intact');
});

test('W7-016 73 (B2): Failed Send, edited draft, late historical turn', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:b2000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b2000000-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'b2111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Original unsent message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null);

  fixture.input.textContent = 'Edited unsent message';
  addTurns(h, [userTurn(h, 'b2222222-2222-4222-8333-333333333333', 'Some other historical turn')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'edited draft + unrelated history must not fabricate a Send');
});

test('W7-016 74 (B3): Failed Send, cleared draft, late historical turn', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:b3000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b3000000-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'b3111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Abandoned unsent message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  fixture.input.textContent = '';
  addTurns(h, [userTurn(h, 'b3222222-2222-4222-8333-333333333333', 'Later historical turn')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'cleared draft + late history fabricates nothing');
});

test('W7-016 75 (B4): Failed Send, edited draft, multiple historical turns', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:b4000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b4000000-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'b4111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Original unsent message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  fixture.input.textContent = 'Edited unsent message';
  const chunks = [
    ['b4222222-2222-4222-8333-333333333333', 'History chunk two'],
    ['b4333333-3333-4222-8333-444444444444', 'History chunk three'],
    ['b4444444-4444-4222-8333-555555555555', 'History chunk four']
  ];
  for (const pair of chunks) {
    addTurns(h, [userTurn(h, pair[0], pair[1])]);
    api.syncSendTrackerFromDOM();
    assert.strictEqual(api.getSendTrackerEntry(convo), null, 'chunk ' + pair[0] + ' must not fabricate a Send');
  }
});

test('W7-016 76 (B5): Persisted previous Send survives all failed scenarios', async () => {
  const { h, api } = setup();
  const convo = 'c:b5000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b5000000-1111-4222-8333-111111111111';
  const prior = Date.now() - 600000;

  api.setSendTrackerEntry(convo, {
    timestamp: prior, turnId: 'b5555555-5555-4222-8333-666666666666', provenance: 'observed'
  });
  addTurns(h, [userTurn(h, 'b5111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Doomed message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  fixture.input.textContent = 'Edited doomed message';
  addTurns(h, [userTurn(h, 'b5222222-2222-4222-8333-333333333333', 'Unrelated history')]);
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.strictEqual(entry.timestamp, prior, 'failed scenarios never reset the persisted timestamp');
  assert.strictEqual(entry.provenance, 'observed');
  assert.strictEqual(entry.turnId, 'b5555555-5555-4222-8333-666666666666');
});

test('W7-016 77 (B6): Successful mouse Send records correct new turn', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:b6000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b6000000-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'b6111111-1111-4222-8333-222222222222', 'Old history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null);

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.input.textContent = 'Click message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.ok(entry, 'accepted mouse Send recorded');
  assert.strictEqual(entry.provenance, 'observed');
  assert.ok(entry.timestamp > 0);
  assert.ok(String(entry.turnId).length > 0, 'recorded turn binds the accepted turn');
});

test('W7-016 78 (B7): Successful keyboard Send records correct new turn', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:b7000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b7000000-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'b7111111-1111-4222-8333-222222222222', 'Old history')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  fixture.input.textContent = 'Enter message';
  fixture.input.dispatchEvent(new FakeEvent('keydown', { key: 'Enter', code: 'Enter' }));
  const keyTurn = userTurn(h, 'b7222222-2222-4222-8333-333333333333', 'Enter message');
  addTurns(h, [keyTurn]);
  fixture.input.textContent = '';
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.ok(entry, 'accepted keyboard Send recorded');
  assert.strictEqual(entry.provenance, 'observed');
  assert.strictEqual(entry.turnId, 'b7222222-2222-4222-8333-333333333333');
});

test('W7-016 79 (B8): Accepted Send text matches the captured authored payload', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:b8000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b8000000-1111-4222-8333-111111111111';

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.input.textContent = 'The quick brown fox';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const latest = api.latestChatGPTUserTurn();
  assert.ok(latest, 'accepted turn visible');
  const candidates = api.userTurnTextCandidates(latest);
  assert.ok(candidates.includes('The quick brown fox'), 'accepted turn carries the authored payload');
  const entry = api.getSendTrackerEntry(convo);
  assert.ok(entry, 'matching payload records the Send');
  assert.strictEqual(entry.provenance, 'observed');
});

test('W7-016 80 (B9): Historical turn text differs from attempted payload', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:b9000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/b9000000-1111-4222-8333-111111111111';

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Alpha attempt payload';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const history = userTurn(h, 'b9222222-2222-4222-8333-333333333333', 'Beta historical content');
  addTurns(h, [history]);
  assert.ok(!api.userTurnTextCandidates(history).includes('Alpha attempt payload'), 'history genuinely differs from payload');
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'mismatched history never corroborates');
});

test('W7-016 81 (B10): Attachment-only submission with verified acceptance', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:ba000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/ba000000-1111-4222-8333-111111111111';

  const fixture = composerFixture(h);
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');

  // Attach-only with no Send: nothing recorded.
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null);

  // Attachment-only Send accepted by ChatGPT: tiles consumed, turn added.
  installAcceptedSend(h, fixture, { consumeAttachment: true });
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  const entry = api.getSendTrackerEntry(convo);
  assert.ok(entry, 'accepted attachment-only Send recorded without visible text');
  assert.strictEqual(entry.provenance, 'observed');
});

test('W7-016 82 (B11): Draft-to-stable transition after accepted Send', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  h.sandbox.location.pathname = '/';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  const draftKey = api.currentConversationKey();
  assert.ok(draftKey.startsWith('draft:'));

  // Operator submits in the draft; the turn lands only after the stable
  // route exists. The armed intent travels with the conversation.
  const fixture = composerFixture(h);
  fixture.input.textContent = 'Draft question';
  fixture.input.dispatchEvent(new FakeEvent('keydown', { key: 'Enter', code: 'Enter' }));
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(draftKey), null, 'no turn yet, nothing recorded');

  h.sandbox.location.pathname = '/c/bb000000-1111-4222-8333-222222222222';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  const stableKey = api.currentConversationKey();
  const stableTurn = userTurn(h, 'bb111111-1111-4222-8333-333333333333', 'Draft question');
  addTurns(h, [stableTurn]);
  fixture.input.textContent = '';
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(stableKey);
  assert.ok(entry, 'in-flight draft Send accepted on the stable route');
  assert.strictEqual(entry.provenance, 'observed');
});

test('W7-016 83 (B12): Navigation invalidates stale manual intent', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convoA = 'c:bc000000-aaaa-4222-8333-111111111111';
  const convoB = 'c:bc000000-bbbb-4222-8333-222222222222';

  h.sandbox.location.pathname = '/c/bc000000-aaaa-4222-8333-111111111111';
  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Failed message on A';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convoA), null);
  fixture.input.textContent = 'Edited message on A';

  // Navigate away: hydrating history on B records nothing.
  h.sandbox.location.pathname = '/c/bc000000-bbbb-4222-8333-222222222222';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  addTurns(h, [userTurn(h, 'bc111111-bbbb-4222-8333-333333333333', 'Chat B history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convoB), null);

  // Returning to A must not resurrect the stale intent.
  h.sandbox.location.pathname = '/c/bc000000-aaaa-4222-8333-111111111111';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  addTurns(h, [userTurn(h, 'bc222222-aaaa-4222-8333-444444444444', 'Chat A late history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convoA), null, 'stale intent died on navigation');
});

test('W7-016 84 (B13): Expired manual intent cannot authorize Send', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:bd000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/bd000000-1111-4222-8333-111111111111';
  let fakeNow = Date.now();
  h.sandbox.Date.now = () => fakeNow;

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'Stale message';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null);

  fakeNow += 35000;
  h.advance(35000);
  addTurns(h, [userTurn(h, 'bd222222-2222-4222-8333-333333333333', 'History after expiry')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'intent past its 30 s window authorizes nothing');
});

test('W7-016 85 (B14): Repeated observation of one turn remains idempotent', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:be000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/be000000-1111-4222-8333-111111111111';

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.input.textContent = 'Idempotent question';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const first = api.getSendTrackerEntry(convo);
  assert.ok(first, 'accepted Send recorded');
  assert.strictEqual(first.provenance, 'observed');

  h.advance(5000);
  api.syncSendTrackerFromDOM();
  h.advance(5000);
  api.syncSendTrackerFromDOM();
  h.advance(5000);
  api.syncSendTrackerFromDOM();

  const last = api.getSendTrackerEntry(convo);
  assert.strictEqual(last.timestamp, first.timestamp, 'repeated observation never moves the clock');
  assert.strictEqual(last.provenance, 'observed');
  assert.strictEqual(last.turnId, first.turnId);
});

test('W7-016 86 (A11): Newer unverified attachment never overwrites Bridge-confirmed canonical', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  composerFixture(h);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });

  // Unverified composer attachment with a NEWER timestamp mounts.
  addComposerAttachmentTile(h, '_AUDAPACK_09.10.26-T08-30-00.zip');
  api.renderTitlebarIndicators();

  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 03:31:16', 'canonical clock survives newer unverified attachment');
  assert.ok(zipEl.title.includes('Attached: _AUDAPACK_09.10.26-T08-30-00.zip'), 'attachment stays separately identifiable');
  const stored = api.getVerifiedProjectArchive('audapack');
  assert.strictEqual(stored.filename, '_AUDAPACK_09.10.26-T03-31-16.zip', 'verified store never absorbs the unverified attachment');
});

test('W7-016 87 (A12): Restored canonical entry is not re-overwritten while newer attachment stays mounted', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  composerFixture(h);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.setManualArchiveBinding({ project_id: 'audapack', display_name: 'AUDAPACK' });
  addComposerAttachmentTile(h, '_AUDAPACK_09.10.26-T08-30-00.zip');
  api.renderTitlebarIndicators();

  // Restore the canonical entry (as an operator/Bridge repair would), keep
  // the newer attachment mounted, render again.
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T03-31-16.zip',
    timestamp: Date.parse('2026-10-09T03:31:16'),
    source: 'archive filename'
  });
  api.renderTitlebarIndicators();

  const zipEl = h.dom.querySelector('#acb-archive-timestamp');
  assert.strictEqual(zipEl.textContent, 'ZIP 03:31:16', 're-render with mounted attachment keeps canonical');
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T03-31-16.zip', 'canonical entry never overwritten again');
});

test('W7-016 88 (B15): Failed Send plus manually cleared duplicate text plus delayed same-text history fabricates nothing', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:bf000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/bf000000-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'bf111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'continue';
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'failed Send records nothing');
  assert.strictEqual(String(fixture.input.textContent), 'continue', 'rejected draft stays in the composer');

  // The operator manually clears the unsent draft: real user editing fires
  // input events, which is the reliable cancellation evidence that retires
  // the failed intent. The widget syncs continuously, so it observes the
  // cleared composer before any delayed history arrives.
  fixture.input.textContent = '';
  fixture.input.dispatchEvent(new FakeEvent('input', { bubbles: true }));
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'cleared draft alone records nothing');

  // Delayed historical hydration carries the SAME text as the attempt.
  addTurns(h, [userTurn(h, 'bf222222-2222-4222-8333-333333333333', 'continue')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'delayed same-text history must not fabricate an accepted Send');
});

test('W7-016 89 (B16): Duplicate-text history after a failed Send preserves the previously persisted timestamp', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:c0000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/c0000000-1111-4222-8333-111111111111';
  const prior = Date.now() - 600000;

  api.setSendTrackerEntry(convo, {
    timestamp: prior, turnId: 'c0555555-5555-4222-8333-666666666666', provenance: 'observed'
  });
  addTurns(h, [userTurn(h, 'c0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  fixture.send._sendFails = true;
  fixture.input.textContent = 'cc';
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  fixture.input.textContent = '';
  fixture.input.dispatchEvent(new FakeEvent('input', { bubbles: true }));
  api.syncSendTrackerFromDOM();

  addTurns(h, [userTurn(h, 'c0222222-2222-4222-8333-333333333333', 'cc')]);
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.strictEqual(entry.timestamp, prior, 'failed duplicate-text scenario never moves the persisted clock');
  assert.strictEqual(entry.turnId, 'c0555555-5555-4222-8333-666666666666');
  assert.strictEqual(entry.provenance, 'observed');
});

// ---------------------------------------------------------------------------
// P1 corrective coverage (post T-298): a Send RECEIPT proves transmission,
// never canonical ownership; manual attachment removal must invalidate a
// pending attachment-only Send intent that no `input` event ever observes.
// ---------------------------------------------------------------------------

const ARCHIVE_METADATA_STORE_KEY = 'audapack_verified_archive_metadata_v1';

function canonicalStoreWrites(h, run) {
  const before = h.gmStore.get(ARCHIVE_METADATA_STORE_KEY) || '';
  run();
  const after = h.gmStore.get(ARCHIVE_METADATA_STORE_KEY) || '';
  return Number(before !== after);
}

test('W7-016 90 (C1): Older Send receipt never overwrites newer canonical metadata', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000000-1111-4222-8333-111111111111';
  composerFixture(h);

  // Bridge-confirmed canonical (newer): 09.10.26 07:50:41
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T07-50-41.zip',
    timestamp: Date.parse('2026-10-09T07:50:41'),
    source: 'archive filename'
  });

  // Accepted receipt transmits an OLDER archive: 08.10.26 05:14:51
  const ok = api.manualArchiveRecordSent({
    conversationKey: convo,
    projectId: 'audapack',
    sha256: '1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  });
  assert.strictEqual(ok, true, 'receipt accepted');

  const stored = api.getVerifiedProjectArchive('audapack');
  assert.strictEqual(stored.filename, '_AUDAPACK_09.10.26-T07-50-41.zip', 'canonical filename unchanged by older receipt');
  assert.strictEqual(stored.timestamp, Date.parse('2026-10-09T07:50:41'), 'canonical timestamp unchanged by older receipt');
});

test('W7-016 91 (C2): Newer Send receipt never overwrites older Bridge-confirmed canonical metadata', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000001-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000001-1111-4222-8333-111111111111';
  composerFixture(h);

  // Bridge-confirmed canonical older than the receipt.
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_07.10.26-T22-05-40.zip',
    timestamp: Date.parse('2026-10-07T22:05:40'),
    source: 'archive filename'
  });

  const ok = api.manualArchiveRecordSent({
    conversationKey: convo,
    projectId: 'audapack',
    sha256: '2222333344445555666677778888999900001111bbbbccccddddeeeeffff0000',
    filename: '_AUDAPACK_09.10.26-T07-50-41.zip'
  });
  assert.strictEqual(ok, true);

  const stored = api.getVerifiedProjectArchive('audapack');
  assert.strictEqual(stored.filename, '_AUDAPACK_07.10.26-T22-05-40.zip', 'timestamp ordering never substitutes for authority');
  assert.strictEqual(stored.timestamp, Date.parse('2026-10-07T22:05:40'));
});

test('W7-016 92 (C3): Receipt acceptance still updates SEND', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000002-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000002-1111-4222-8333-111111111111';
  composerFixture(h);

  const ok = api.manualArchiveRecordSent({
    conversationKey: convo,
    projectId: 'audapack',
    sha256: '3333444455556666777788889999000011112222ccccddddeeeeffff00001111',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  });
  assert.strictEqual(ok, true);

  const entry = api.getSendTrackerEntry(convo);
  assert.ok(entry, 'receipt updates SEND');
  assert.strictEqual(entry.provenance, 'receipt');
  api.renderTitlebarIndicators();
  assert.strictEqual(h.dom.querySelector('#acb-send-age').textContent, 'SEND 00:00:00');
});

test('W7-016 93 (C4): Repeated receipt is idempotent and writes canonical store zero times', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000003-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000003-1111-4222-8333-111111111111';
  composerFixture(h);

  const receipt = {
    conversationKey: convo,
    projectId: 'audapack',
    sha256: '4444555566667777888899990000111122223333ddddeeeeffff000011112222',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  };

  const writes = canonicalStoreWrites(h, () => {
    assert.strictEqual(api.manualArchiveRecordSent(receipt), true);
    assert.strictEqual(api.manualArchiveRecordSent(receipt), true);
    assert.strictEqual(api.manualArchiveRecordSent(receipt), true);
  });
  assert.strictEqual(writes, 0, 'receipt processing performs zero canonical-store writes');

  const keys = Array.from(h.gmStore.keys());
  assert.ok(!keys.some(k => k === ARCHIVE_METADATA_STORE_KEY) || !h.gmStore.get(ARCHIVE_METADATA_STORE_KEY) || !String(h.gmStore.get(ARCHIVE_METADATA_STORE_KEY)).includes('audapack'), 'canonical store never holds receipt metadata');

  // Exactly-once bookkeeping: one entry for the (key, project, sha) identity.
  const store = api.manualArchiveSentStore();
  const matches = store.entries.filter(e => e.key === convo && e.project_id === 'audapack');
  assert.strictEqual(matches.length, 1, 'repeated receipt keeps a single transaction entry');
});

test('W7-016 94 (C5): Receipt retains its own identity separately from canonical', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000004-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000004-1111-4222-8333-111111111111';
  composerFixture(h);

  const sha = '5555666677778888999900001111222233334444eeeeffff0000111122223333';
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T07-50-41.zip',
    timestamp: Date.parse('2026-10-09T07:50:41'),
    source: 'archive filename'
  });

  assert.strictEqual(api.manualArchiveRecordSent({
    conversationKey: convo, projectId: 'audapack', sha256: sha,
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  }), true);

  const sent = api.manualArchiveSentEntry(convo, 'audapack', sha);
  assert.ok(sent, 'transmitted archive available through its receipt identity');
  assert.strictEqual(sent.sha256, sha);
  assert.strictEqual(sent.filename, '_AUDAPACK_08.10.26-T05-14-51.zip');
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T07-50-41.zip', 'canonical untouched');
});

test('W7-016 95 (C6): Receipt filename never lands in canonical store', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000005-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000005-1111-4222-8333-111111111111';
  composerFixture(h);

  // No canonical set, no Bridge token — receipt triggers a background refresh
  // that fails offline (no token). The receipt filename must NOT appear in the
  // canonical store regardless.
  assert.strictEqual(api.manualArchiveRecordSent({
    conversationKey: convo, projectId: 'audapack',
    sha256: '6666777788889999000011112222333344445555ffff00001111222233334444',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  }), true);
  await h.settle();
  assert.strictEqual(api.getVerifiedProjectArchive('audapack'), null, 'receipt writes nothing to the canonical store');
  // Explicit Bridge confirmation then updates canonical independently.
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  const state = { requests: 0, fail: false, projectId: 'audapack', filename: '_AUDAPACK_09.10.26-T06-00-00.zip', mtime: Date.parse('2026-10-09T06:00:00') };
  bridgeMetadataResponder(h, state);
  const pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T06-00-00.zip', 'Bridge confirmation updates canonical');
  // Receipt filename never landed.
  assert.notStrictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_08.10.26-T05-14-51.zip');
});

test('W7-016 96 (C7): Bridge-confirmed older archive replacement still succeeds after receipt', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000006-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000006-1111-4222-8333-111111111111';
  composerFixture(h);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T04-45-00.zip',
    timestamp: Date.parse('2026-10-09T04:45:00'),
    source: 'archive filename'
  });

  // Bridge responder set so the receipt's background refresh reaches it.
  // The receipt filename must NOT be the one that lands; the Bridge
  // confirms a legitimately OLDER canonical identity.
  const state = { requests: 0, fail: false, projectId: 'audapack', filename: '_AUDAPACK_07.10.26-T22-05-40.zip', mtime: Date.parse('2026-10-07T22:05:40') };
  bridgeMetadataResponder(h, state);

  api.manualArchiveRecordSent({
    conversationKey: convo, projectId: 'audapack',
    sha256: '7777888899990000111122223333444455556666000011112222333344445555',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  });
  await h.settle();
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_07.10.26-T22-05-40.zip', 'receipt triggers bounded refresh; Bridge confirms older canonical');
});

test('W7-016 97 (C8): Bridge offline preserves previously confirmed metadata despite receipt', async () => {
  const { h, api } = setup();
  api.storage.gmSet('ai_chatbuttons_bridge_token_v1', 'test-token');
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000007-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000007-1111-4222-8333-111111111111';
  composerFixture(h);

  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T07-50-41.zip',
    timestamp: Date.parse('2026-10-09T07:50:41'),
    source: 'archive filename'
  });

  h.httpResponder = () => { throw new Error('Failed to connect to Bridge: ECONNREFUSED'); };
  api.manualArchiveRecordSent({
    conversationKey: convo, projectId: 'audapack',
    sha256: '8888999900001111222233334444555566667777000011112222333344445555',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  });
  const pending = api.refreshProjectArchiveMetadata('audapack');
  await h.settle();
  await pending;

  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T07-50-41.zip', 'cached canonical survives offline + receipt');
});

test('W7-016 98 (C9): Project A receipt cannot touch Project B canonical metadata', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000008-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000008-1111-4222-8333-111111111111';
  composerFixture(h);

  api.setVerifiedProjectArchive('proj-b', {
    filename: '_PROJB_09.10.26-T07-50-41.zip',
    timestamp: Date.parse('2026-10-09T07:50:41'),
    source: 'archive filename'
  });

  api.manualArchiveRecordSent({
    conversationKey: convo, projectId: 'proj-a',
    sha256: '9999000011112222333344445555666677778888000011112222333344445555',
    filename: '_PROJA_08.10.26-T05-14-51.zip'
  });

  assert.strictEqual(api.getVerifiedProjectArchive('proj-a'), null, 'receipt writes nothing for its own project');
  assert.strictEqual(api.getVerifiedProjectArchive('proj-b').filename, '_PROJB_09.10.26-T07-50-41.zip', 'other project untouched');
});

test('W7-016 99 (C10): Manual receipt and automatic archive transaction coexist', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  const convo = 'c:d0000009-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/d0000009-1111-4222-8333-111111111111';
  composerFixture(h);

  // Manual receipt for audapack.
  assert.strictEqual(api.manualArchiveRecordSent({
    conversationKey: convo, projectId: 'audapack',
    sha256: 'aaaa000011112222333344445555666677778888000011112222333344445555',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  }), true);

  // Automatic runtime write for the same project remains authoritative.
  api.setVerifiedProjectArchive('audapack', {
    filename: '_AUDAPACK_09.10.26-T07-50-41.zip',
    timestamp: Date.parse('2026-10-09T07:50:41'),
    source: 'archive filename'
  });
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T07-50-41.zip');

  // Receipt again after auto write: canonical still intact.
  assert.strictEqual(api.manualArchiveRecordSent({
    conversationKey: convo, projectId: 'audapack',
    sha256: 'aaaa000011112222333344445555666677778888000011112222333344445555',
    filename: '_AUDAPACK_08.10.26-T05-14-51.zip'
  }), true);
  assert.strictEqual(api.getVerifiedProjectArchive('audapack').filename, '_AUDAPACK_09.10.26-T07-50-41.zip', 'automatic transaction unaffected by receipt');
  assert.ok(api.manualArchiveSentEntry(convo, 'audapack', 'aaaa000011112222333344445555666677778888000011112222333344445555'), 'manual receipt identity preserved');
});

test('W7-016 100 (D1): Failed attachment-only Send, mouse removal, delayed history fabricates nothing', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:e0000000-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/e0000000-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'e0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send._sendFails = true;
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'rejected Send records nothing');
  assert.ok(tile.isConnected, 'tile still attached after rejection');

  // Operator clicks the tile's removal control: no `input` event fires on the
  // contenteditable, which is exactly the real ChatGPT behaviour.
  const remove = tile.querySelector('button[aria-label^="Remove"]');
  assert.ok(remove, 'removal control present');
  remove.dispatchEvent(new FakeEvent('click', { bubbles: true }));
  tile.remove();
  h.mutate(fixture.form);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'removal alone records nothing');

  // Delayed historical hydration of an unrelated user turn.
  addTurns(h, [userTurn(h, 'e0222222-2222-4222-8333-333333333333', 'Unrelated historical turn')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'delayed history must not resurrect a cancelled attachment-only Send');
});

test('W7-016 101 (D2): Cancelled attachment-only intent preserves previous SEND timestamp', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:e0000001-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/e0000001-1111-4222-8333-111111111111';
  const prior = Date.now() - 600000;

  api.setSendTrackerEntry(convo, { timestamp: prior, turnId: 'e0555555-5555-4222-8333-666666666666', provenance: 'observed' });
  addTurns(h, [userTurn(h, 'e0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send._sendFails = true;
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const remove = tile.querySelector('button[aria-label^="Remove"]');
  remove.dispatchEvent(new FakeEvent('click', { bubbles: true }));
  tile.remove();
  h.mutate(fixture.form);
  api.syncSendTrackerFromDOM();

  addTurns(h, [userTurn(h, 'e0222222-2222-4222-8333-333333333333', 'Later history')]);
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.strictEqual(entry.timestamp, prior, 'cancelled attachment-only Send never moves the clock');
  assert.strictEqual(entry.turnId, 'e0555555-5555-4222-8333-666666666666');
});

test('W7-016 102 (D3): Attachment replacement invalidates the pending intent', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:e0000002-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/e0000002-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'e0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  const tileA = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send._sendFails = true;
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  // Operator replaces the archive: removes A, attaches B.
  const removeA = tileA.querySelector('button[aria-label^="Remove"]');
  removeA.dispatchEvent(new FakeEvent('click', { bubbles: true }));
  tileA.remove();
  addComposerAttachmentTile(h, '_AUDAPACK_09.10.26-T07-50-41.zip');
  h.mutate(fixture.form);
  api.syncSendTrackerFromDOM();

  addTurns(h, [userTurn(h, 'e0222222-2222-4222-8333-333333333333', 'Delayed history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'replacement cancels the stale attachment-only intent');
});

test('W7-016 103 (D4): Genuine accepted attachment-only Send still records', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:e0000003-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/e0000003-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'e0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture, { consumeAttachment: true });
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const entry = api.getSendTrackerEntry(convo);
  assert.ok(entry, 'genuine accepted attachment-only Send records');
  assert.strictEqual(entry.provenance, 'observed');
});

test('W7-016 104 (D5): Programmatic tile consumption during accepted Send is not cancellation', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:e0000004-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/e0000004-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'e0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  // Install a Send that consumes the attachment programmatically WITHOUT any
  // click on a removal control (page-controlled consumption).
  installAcceptedSend(h, fixture, { consumeAttachment: true });
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  assert.ok(api.getSendTrackerEntry(convo), 'page-controlled consumption is acceptance, never manual cancellation');
});

test('W7-016 105 (D6): Document-delegated removal invalidates pending intent without a composer input event', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  // Exercise the REAL document-level delegated listener: dispatch the removal
  // click on the button so it bubbles to document, never a synthetic input.
  h.sandbox.location.pathname = '/c/e0000005-1111-4222-8333-111111111111';
  const convo = 'c:e0000005-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'e0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send._sendFails = true;
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const remove = tile.querySelector('button[aria-label^="Remove"]');
  // Click originates at the remove control; bubbles (and capture-phase
  // document listener) observe the intent before any page handler runs.
  remove.dispatchEvent(new FakeEvent('click', { bubbles: true }));
  tile.remove();
  h.mutate(fixture.form);
  api.syncSendTrackerFromDOM();

  addTurns(h, [userTurn(h, 'e0222222-2222-4222-8333-333333333333', 'Delayed unrelated history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'delegated removal click invalidates the pending attachment-only intent');
});

test('W7-016 106 (D7): Keyboard activation of a removal control invalidates the intent', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:e0000006-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/e0000006-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'e0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send._sendFails = true;
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const remove = tile.querySelector('button[aria-label^="Remove"]');
  // Keyboard activation (Enter/Space on a focused button).
  const keyEvt = new FakeEvent('keydown', { key: 'Enter', bubbles: true });
  keyEvt.target = remove;
  h.dom.dispatchEvent(keyEvt);
  tile.remove();
  h.mutate(fixture.form);
  api.syncSendTrackerFromDOM();

  addTurns(h, [userTurn(h, 'e0222222-2222-4222-8333-333333333333', 'Delayed unrelated history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'keyboard removal invalidates the pending attachment-only intent');
});

test('W7-016 107 (D8): React remount (tile disconnected without a removal event) fabricates nothing', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convo = 'c:e0000007-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/e0000007-1111-4222-8333-111111111111';

  addTurns(h, [userTurn(h, 'e0111111-1111-4222-8333-222222222222', 'Old history one')]);
  api.syncSendTrackerFromDOM();

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send._sendFails = true;
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  // Remount: the tile is detached by React with NO removal interaction at all.
  tile.remove();
  h.mutate(fixture.form);
  api.syncSendTrackerFromDOM();

  addTurns(h, [userTurn(h, 'e0222222-2222-4222-8333-333333333333', 'Post-remount history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convo), null, 'a disconnected tile plus unrelated new turn is never acceptance evidence');
});

test('W7-016 108 (D9): Navigation invalidates a stale attachment-only intent', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  const convoA = 'c:e0000008-aaaa-4222-8333-111111111111';
  const convoB = 'c:e0000008-bbbb-4222-8333-222222222222';

  h.sandbox.location.pathname = '/c/e0000008-aaaa-4222-8333-111111111111';
  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send._sendFails = true;
  fixture.send.click();
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convoA), null);

  // Navigate away mid-intent.
  h.sandbox.location.pathname = '/c/e0000008-bbbb-4222-8333-222222222222';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  addTurns(h, [userTurn(h, 'e0222222-bbbb-4222-8333-333333333333', 'Chat B history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convoB), null);

  // Return: the stale attachment-only intent must not resurrect.
  h.sandbox.location.pathname = '/c/e0000008-aaaa-4222-8333-111111111111';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  addTurns(h, [userTurn(h, 'e0222222-aaaa-4222-8333-444444444444', 'Chat A late history')]);
  api.syncSendTrackerFromDOM();
  assert.strictEqual(api.getSendTrackerEntry(convoA), null, 'navigation invalidates the stale attachment-only intent');
});

test('W7-016 109 (D10): Draft-to-stable migration keeps a cancelled attachment-only intent cancelled', async () => {
  const { h, api } = setup();
  api.clearSendTrackerStore();
  h.sandbox.location.pathname = '/';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  const draftKey = api.currentConversationKey();
  assert.ok(draftKey.startsWith('draft:'));

  const fixture = composerFixture(h);
  installAcceptedSend(h, fixture);
  const tile = addComposerAttachmentTile(h, '_AUDAPACK_08.10.26-T05-14-51.zip');
  fixture.send._sendFails = true;
  fixture.send.click();
  api.syncSendTrackerFromDOM();

  const remove = tile.querySelector('button[aria-label^="Remove"]');
  remove.dispatchEvent(new FakeEvent('click', { bubbles: true }));
  tile.remove();
  h.mutate(fixture.form);
  api.syncSendTrackerFromDOM();

  // ChatGPT assigns a stable route and hydrates an unrelated turn.
  h.sandbox.location.pathname = '/c/e0000009-1111-4222-8333-555555555555';
  api.bindAutoRuntimeToCurrentConversation({ claim: false });
  const stableKey = api.currentConversationKey();
  addTurns(h, [userTurn(h, 'e0222222-1111-4222-8333-666666666666', 'Stable route history')]);
  api.syncSendTrackerFromDOM();

  assert.strictEqual(api.getSendTrackerEntry(stableKey), null, 'migration never revives a cancelled attachment-only intent');
});

test('W7-016 110 (D11): Repeated identical filenames preserve transaction identity and idempotency', async () => {
  const { h, api } = setup();
  api.clearVerifiedProjectArchives();
  const convo = 'c:e0000010-1111-4222-8333-111111111111';
  h.sandbox.location.pathname = '/c/e0000010-1111-4222-8333-111111111111';
  composerFixture(h);

  const sha = 'bbbb000011112222333344445555666677778888000011112222333344445555';
  const receipt = { conversationKey: convo, projectId: 'audapack', sha256: sha, filename: '_AUDAPACK_08.10.26-T05-14-51.zip' };
  assert.strictEqual(api.manualArchiveRecordSent(receipt), true);
  assert.strictEqual(api.manualArchiveRecordSent(receipt), true);

  const store = api.manualArchiveSentStore();
  const matches = store.entries.filter(e => e.key === convo && e.project_id === 'audapack' && e.sha256 === sha);
  assert.strictEqual(matches.length, 1, 'identical filename + sha keeps a single transaction identity');
  assert.ok(matches[0].at > 0);
});
