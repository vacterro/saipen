# AUDAPACK Widget — production delivery acceptance record

This file is the OPERATOR acceptance record for the Tampermonkey widget. It
exists because a userscript reaches an installed browser through a path no
pytest suite can fully drive: the browser's own userscript manager decides,
from a version comparison alone, whether to replace the script it already has.

Filed by T-196 after a real defect: materially different widget bytes shipped
under an unchanged `@version` (`0.0.59` -> `0.0.59`), so the repository, its
tests and the served endpoint all exercised the new build while an installed
browser kept running the old one.

## What is proven by machine

| Check | Where |
| --- | --- |
| Shipped bytes match the recorded release, and different bytes cannot keep the same `@version` | `tests/test_widget_release_identity.py` |
| The RECORDER enforces monotonic release identity: same-version changed bytes and downgrades are refused with zero mutation, a strictly greater version records, a repeat is an idempotent no-op, a first record is an explicit `--bootstrap`, a malformed ledger fails closed, and a failed write never destroys the previous ledger | `tests/test_widget_release_recorder.py` |
| The REAL endpoint `GET /widget.user.js` serves the recorded release, with a javascript Content-Type, the new `@version`, and one `@updateURL`/`@downloadURL` pair pointing at this Bridge | `tests/test_bridge_widget_delivery.py` |
| The update probe's verdict flips when the Bridge serves an older or unrecorded build, and orders versions through the same canonical comparator as the recorder | `tests/test_widget_update_probe.py` |
| Widget behaviour against a real Bridge and real Chromium | `tests/test_browser_bridge_widget_integration.py` (SYNTHETIC ChatGPT DOM) |

## Live chatgpt.com generation-control evidence (T-259, widget 0.0.86)

No synthetic DOM can prove which control the real site actually mounts, so the
generation Stop's identity was captured from the live site in the AUDAPACK
dedicated Chromium profile on 2026-09-29, mid-generation, with a real turn
running. Structure only — no conversation text, prompt, account data or token
was recorded.

```text
form.relative.flex.flex-col.gap-2                 (no data-type="unified-composer")
  div[contenteditable][role=textbox].ProseMirror[aria-label="Ask ChatGPT"]
  div.ComposerLayoutFooter-_8IVRO
    div.min-w-0.max-sm:col-start-3.max-sm:row-start-2
      div.flex.min-w-0.items-center.justify-end.shrink-0
        div.flex.shrink-0.items-center.gap-2
          div.flex.items-center
            button[type=button][aria-label="Stop"]     <- the live generation Stop
              svg.icon-primary-action[aria-hidden]      <- the square glyph
            button[aria-label="Dictate"][disabled]
          button[aria-label="Select ChatGPT model"]
  button[aria-label="Add files and more"]               <- leading slot
```

At idle the same trailing slot holds `button[aria-label="Start Voice"]`, and the
Stop replaces it: one action slot, two states, exactly the composer-action
semantics generation truth depends on. The control carries no `data-testid`, no
`id` and no `role`, which is why 0.0.85's tightened identity list (built on the
older `stop-button` / `Stop generating` / `Stop streaming` markers) did not match
it and the widget reported `READY` on two simultaneously generating audit tabs.
The full capture is in `.saipen/evidence/T-259-generation-stop.html.md`.

Note for future probes: `scripts/probe_chatgpt_generation.py` uses debug port
`9224`, which on this machine is already taken by an unrelated application
(Freebuff) whose own UI carries a `Stop the running turn` button. A probe that
connects there reads a foreign page and reports it as ChatGPT. Use a free port
and assert `location.origin` before trusting a capture.

## Reading the widget's own verdict (T-260)

A stale userscript and a stale detector are indistinguishable from outside the
tab: the widget disagrees with the page, and nothing on screen says which build
is answering. After 0.0.88 the compact cell answers it on hover — its tooltip
reads `AUDAPACK Widget <installed @version> - generation: <state> (<reason>)`.
Check that one line first when the widget and the page disagree:

| Tooltip | Meaning | Action |
| --- | --- | --- |
| `generation: generating (canonical-stop-owned, saw canonical-stop-current-build)` | the live Stop was found and accepted | nothing; this is correct |
| `generation: idle (no-composer)` | the composer was not found at all | the tab is not a ChatGPT conversation, or the page has not mounted its composer |
| `generation: idle (stale_stop_candidate_ignored, saw stop-like)` plus a cell reading `ATTN` | generation-shaped chrome was found inside the current composer and could not be identified | the detector is behind the site's build; the full identity is in the Bridge worker record |
| an `@version` below the Bridge's `required_widget_build` | the tab is running an old build | reload the ChatGPT tab; Tampermonkey applies the update on load |

`ATTN` on the compact cell is deliberately not a failure of the audit: it means
the widget refuses to say READY while it can see something it cannot explain.

## What the operator must do once (not automatable)

Tampermonkey's dashboard exposes no scriptable update API, so these steps are
performed by hand and recorded below. Run them in the browser profile that
actually hosts the widget.

### 1. Confirm the served build

```bash
python scripts/widget_update_probe.py --installed-version <version-in-Tampermonkey-dashboard>
```

`VERDICT: PASS` means the Bridge is offering a strictly newer, recorded release
through the supported delivery path. If it says FAIL, stop: no amount of
browser-side clicking will update an installed script.

### 2. Let the installed script update

Open Tampermonkey's dashboard, select **AUDAPACK Widget**, and confirm the
version shown becomes the new one (an interval check updates it on its own;
*Update* forces it).

### 3. Collapsed widget (real ChatGPT)

- toolbar is readable; controls are not crushed into fragments
- the bound project identity is understandable
- the ZIP action is reachable
- the settings / expand action is reachable

### 4. Project picker (real ChatGPT)

- opens as a bounded popover and does not crush the underlying widget
- full project names are distinguishable; long names carry a full tooltip
- the list scrolls
- outside click closes; Escape closes; a selection closes
- no horizontal viewport overflow

### 5. Expanded widget (real ChatGPT)

- settings remain usable
- the project picker does not create a broken nested layout
- the widget stays inside the viewport
- the panel remains movable / recoverable

Smoke-check the same three sections at 100%, 125% and 150% browser zoom.

### 6. Normal ZIP transaction semantics (real installed widget, 0.0.61)

Use a normal real ChatGPT conversation. Auto Audit off.

**FIRST NORMAL ZIP.** Choose a registered project and click ZIP. The
transaction proves/prepares the canonical archive, attaches it, waits for the
ready tile, then automatically Sends and positively verifies the Send.

- result `SENT`; exactly one Send, and it is accepted -- no manual Send click;
- exactly one resulting ChatGPT user turn carrying the payload that was
  authored in the composer at click time (text plus any unrelated attachments
  the operator had added); the widget submits, it never rewrites the text;
- the submitted payload leaves the composer as a real accepted Send does;
- no audit campaign / A3 / A10 / START side effects.

**IDENTICAL SECOND ZIP (unchanged project source, unchanged payload).** Repeat
the identical ZIP transaction -> `ALREADY_SENT`.

- the canonical ensure may perform its metadata freshness proof;
- zero archive GET, zero File construction, zero attachment injection, zero
  second Send, no duplicate ChatGPT user turn.

(Do not expect `ALREADY_ATTACHED` here: after the first message has been sent,
the original composer attachment is gone. `ALREADY_ATTACHED` is the transport
state only while the proven canonical archive is still physically attached in
the current composer before Send -- see below.)

**SAME ARCHIVE + DIFFERENT COMPOSER TEXT.** With the proven canonical archive
attached but not yet sent, author a genuinely different payload and click ZIP
-> `ALREADY_ATTACHED` transport state, then a new Send is allowed:

- zero archive GET and zero injection (the verified byte cache may serve the
  same canonical archive); Send exactly once; accepted -> `SENT`.

**ATTACH-ONLY ESCAPE HATCH.** The explicit attach-only action attaches the
canonical archive and performs zero Send. It exists to leave a ready archive
in the composer, not to deliver it.

**RAPID CLICKS while one operation is active.** One effective ensure chain, at
most one effective GET, one injection, one accepted Send, one verified
outgoing message; the coalesced callers receive the same transaction result
semantics. No duplicate ChatGPT turns.

**SEND UNAVAILABLE.** If the archive becomes ready but ChatGPT never becomes
sendable, the transaction ends in the bounded `SEND_TIMEOUT` (or
`SEND_PENDING` when a click happens without positive acceptance) and keeps the
ready archive and the authored payload in the composer; no success receipt is
written. After Send availability is restored, the next ZIP click reuses the
same ready archive: zero redundant GET, zero injection, Send only, verified
`SENT`.

**COMPOSER EDIT DURING PACK/ATTACH.** If the operator edits the composer while
the archive is packing, downloading or registering, the automatic Send is
canceled (`COMPOSER_CHANGED_BEFORE_SEND`); the operator's edit is preserved
and the ready archive is kept.

**NAVIGATION DURING THE TRANSACTION.** If the conversation changes while the
transaction is in flight, it ends `conversation_changed`: the origin
transaction never Sends in the destination chat and its bytes never appear
there.

### 7. Changed-source replacement (real installed widget)

1. modify one harmless project source file;
2. click ZIP again -> source change detected; a fresh canonical archive is
   generated; the SHA changes; the new archive attaches (the previous
   same-project archive stays until the new tile is READY and is removed only
   after a successful replacement; unrelated attachments survive); the
   transaction then automatically Sends and verifies the Send -> `SENT`;
3. one further unchanged click -> `ALREADY_SENT` with no redundant work.

### 8. Cross-chat and multi-tab (real installed widget)

- Chat A binds Project A; Chat B binds Project B; navigate A -> B -> A: the
  bindings stay independent and archive proofs / statuses do not leak.
- Live navigation race: start ZIP in Chat A, navigate to Chat B before it
  completes, start ZIP in Chat B -> A returns `conversation_changed`, A does not
  join B's single-flight, B completes normally, and A's bytes never appear in B.
- Multi-tab: two fresh ChatGPT tabs bind different projects before stable
  conversation ids exist -> both temporary bindings survive independently and
  one tab does not delete the other's temporary binding.

### 9. Managed OpenCode launch (real click)

One operator click: Project Room -> **OpenCode** on a real project. Confirm a
live window after 10 s, the correct bound project root and lineage, a valid
canonical actor, an active guard, and no `ACTOR_UNBOUND`, `GUARD_UNREACHABLE`,
`FLEET_OUTPUT_INVALID` or `CANONICAL_RUNTIME_SOURCE_UNPROVEN` error.

### Operator evidence to record

Fill the row below only from observed results. Required fields: installed widget
before, installed widget after, Bridge version, Bridge SHA, probe verdict, real
collapsed, real picker, real expanded, 100/125/150 zoom, first ZIP (SENT and
positively verified), identical repeat (`ALREADY_SENT`), same archive +
different composer text (new Send allowed), Send-unavailable retry, rapid
clicks, changed-source replacement (SENT), composer-edit cancel, attach-only
escape hatch, cross-chat, multi-tab, navigation race, and the real OpenCode
smoke.

## Recorded acceptances

The CURRENT required ZIP procedure is the auto-Send contract in sections 6-7
(Widget 0.0.61). Rows recorded before that contract keep their historical
evidence verbatim; do not rewrite them. A row may claim ONLY what the operator
observed in that run.

Add one row per acceptance run. Evidence column: the probe receipt path, the
version reported by the Tampermonkey dashboard before and after, and the
result of sections 3-6.

| Date | Machine | Bridge version | Installed before | Installed after | Probe | Sections 3-6 | Operator |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-09-17 | Windows/win32 | 0.0.60 | 0.0.59 (assumed previous delivery) | _pending operator step_ | _pending_ | _pending_ | _pending_ |
| 2026-09-18 | Windows/win32 | 0.0.60 | 0.0.60 | 0.0.60 (no update required) | FAIL (served 0.0.60 not strictly newer) | _pending operator step_ | _pending_ |

> The 2026-09-17 row records the T-196 code-side correction. The installed
> browser step and the real-DOM sections are intentionally left `_pending_`
> until a human runs them: claiming them from this session would repeat exactly
> the mistake T-196 was filed for -- reporting delivery from repository
> evidence.
>
> The 2026-09-18 row records the T-198 production-acceptance run. Its
> `Installed` columns were read, not inferred: the AUDAPACK Tampermonkey record
> was recovered from the real managed worker profile store
> (`...\AUDAPACK\browser_worker\chromium_profile\Default\Local Extension
> Settings\dhdgffkkebhmkfjojejmpbldmpobfkfo`), where the AUDAPACK Widget script
> carries `@version 0.0.60`. The served build equals the installed build, so the
> supported probe correctly answers FAIL on `served_version_is_newer` (0.0.60
> is not strictly greater than 0.0.60) while every delivery check passes; there
> is no update to perform. Probe receipt:
> `%LOCALAPPDATA%\AUDAPACK\logs\widget_update_probe_20260918.json`. The old
> Brave profile store still holds `0.0.02` and is not the widget-hosting profile.
>
> The real-DOM sections (3-6) and the managed OpenCode click remain `_pending_`
> because they require a live operator session; this run did not perform them.

## A3 pre-START delivery on the real ChatGPT build (Widget 0.0.76)

On 2026-09-27 a six-project A3 launch produced six identical `BLOCKED
PRE-START` rows at 0/3 waves: every managed window sat on a clean root chat
with no ZIP tile and no Core turn sent. The Bridge held a valid archive for all
six, so the ZIP bytes were never the problem; delivery stopped at the
composer's file input. This section is the live acceptance for that repair and
is NOT satisfiable from repository evidence.

1. Install the served build through the supported path (sections 1-2 above).
   The served build is 0.0.76.
2. Read the live composer shape the Bridge now holds for every worker:

   ```bash
   python scripts/widget_update_probe.py --installed-version <version-in-Tampermonkey-dashboard>
   curl -s -H "X-AUDAPACK-Token: <token>" http://127.0.0.1:<port>/v1/browser/status      | python -c "import json,sys;[print(w['worker_id'], w.get('upload_topology','')) for w in json.load(sys.stdin)['workers']]"
   ```

   A populated `upload_topology` line means the current ChatGPT build's real
   file-input shape is now known without guessing at a screenshot. A worker
   running an older build reports an empty string; that is the stale-build
   signal, not a DOM problem.
3. One real lane, in the managed worker profile. Required state sequence in
   Audit Runs: `QUEUED -> LEASED -> ARTIFACT_FETCHED -> ATTACHED ->
   START_PREPARED -> STARTED -> AUDITING`, with the correct project ZIP tile
   visible in the composer before Send.
4. One complete real A3 campaign: wave 1 saved, wave 2 saved, wave 3 saved,
   canonical final handoff written, run `READY`.
5. Multi-project batch, 6 projects / max 6 lanes. If only three physical
   workers exist, jobs may queue honestly -- do not manufacture six browsers to
   satisfy the number six. Required: no shared pre-START attachment failure,
   every claimed window receives its own correct project ZIP, no ZIP crosses
   project identity, no human draft or attachment is overwritten, lanes advance
   past 0/3 and completed lanes reach `READY`.
6. Manual ZIP door, same build: attach PASS, attach + Send PASS, an unrelated
   human attachment survives, an attachment identity mismatch fails closed.

When a lane still blocks, Copy Details on the Audit Runs row carries the exact
code and a bounded observation of the composer shape, for example
`upload-input-unavailable | composer=form attach=1 file_inputs=0
verdict=upload-input-unavailable`. `...ambiguous` means more than one candidate
and names them; `composer-root-unavailable` means the composer itself was not
on the page. Record which one you saw.

## Live audit state truth: READY is never shown while generating (Widget 0.0.82)

On 2026-09-28 several managed audit chats were visibly streaming (canonical Core
turn on screen, ChatGPT Thinking / Stop generating, A3 enabled, an active
"Auditing Archive Contents..." wave) while the compact widget read `READY`. This
section is the live acceptance for the T-249 repair and is NOT satisfiable from
repository evidence.

1. Install the served build through the supported path (sections 1-2 above).
   The served build is 0.0.82.
2. Scenario 1 — one registered project chat. Enable A3, START Audit Core. While
   ChatGPT visibly shows Thinking / Stop:
   - the widget MUST NOT say `READY`;
   - it MUST show the active wave (`CORE`, then `W2`, then `PERF` for Quick3);
   - the runtime reaches `wait-<first-wave>`.
   Let the response complete and confirm normal COMPLETE / save / next-wave
   behaviour is unchanged.
3. Scenario 2 — reproduce the operator screenshot: at least `_ZAICODE`,
   `_AUDAPACK` and `FastPrompter` auditing at the same time. While each is
   actively generating, NONE may display `READY`; each shows its own actual
   active wave (Super10 waves show `W1`..`W10`, Compress Audit shows its own
   wave).
4. Scenario 3 — reload / hydrate a tab while an audit is already streaming.
   Required: A3 stays enabled; the runtime reconstructs automatically even when
   the audit user turn finishes hydrating purely through `characterData` (no new
   turn node, no childList event) because enabled+idle+generating opens a
   bounded characterData recovery window that re-arms canonical reconciliation;
   no manual Resume; no `READY` lie; no duplicate wave Send.
5. Ordinary (non-audit) ChatGPT generation in an enabled chat shows `BUSY`, not
   `READY`, and MUST NOT arm or adopt an audit runtime.

## Managed A3 ownership: one lane, one authority (Widget 0.0.84)

Install the served build through the supported path (sections 1-2 above). The
served build is 0.0.84,
`sha256 a0fa7f257d4d2e3c3e2eba521f6b070a00c418bc5d202ca65619dafa2c17d4bf`.

SRC-098 was a CROSS-LAYER split brain: the Bridge Project Room held a live
managed lane (`AUDIT 0/3`, `worker Chrome #1`) while the widget for that exact
window rendered `A3 OFF` and `CHAT`. 0.0.83 repaired the half where the runtime
went dark on its own. 0.0.84 closes the other half: an explicit operator OFF on
a managed worker now retires the Bridge dispatch instead of stranding it.

### Machine-proven (synthetic regression surface)

```bash
node --test tests/widget/w5-001-managed-a3-ownership.test.js
node --test tests/widget/w7-003-live-generation-state.test.js
node --test tests/widget/w7-004-hydration-miss-recovery.test.js
python -m pytest -q tests/test_browser_dispatch.py tests/test_browser_dispatch_http.py
python -m pytest -q tests/test_widget_release_identity.py tests/test_bridge_widget_delivery.py
```

The Bridge side is proven in its own right, not only through the widget:
`test_abandon_retires_a_live_auditing_dispatch_for_an_operator_stop` and
`test_an_explicit_operator_stop_retires_a_live_managed_dispatch` drive a real
dispatch to `AUDITING` over the wire and prove the stop makes it terminal
`FAILED`, releases the worker lease, keeps `campaign_run_id` / `start_receipt`
for Audit Runs history, never re-leads the dispatch, and answers a repeat call
as an ACK with an unchanged `completed_at`.

- **Stale disabled runtime + active managed dispatch -> auto re-arm.** A live
  non-terminal dispatch outranks a stale local `enabled=false`, blank or not.
  The compact label never stays `CHAT`; the current wave identity survives; no
  duplicate Core is sent.
- **Interrupted Core -> campaign retained, wave held.** A stopped answer is
  neither `DONE` nor `CHAT`: the campaign stays at 0/3 in a paused/attention
  state, the interruption reason is reported to the lane, and no duplicate Core
  is sent. This state reconstructs identically after a reload.
- **Explicit operator OFF -> canonical Bridge stop.** One
  `POST /v1/browser/jobs/{dispatch_id}/abandon`, which the Bridge already
  defines as terminal `FAILED` with `operator_abandoned`: the lane stops
  occupying the worker pool, the record stays in Audit Runs history, and the
  dispatch is never re-leased or re-STARTed. `CANCELLED` is deliberately not
  used — it asserts that no Core was sent and is illegal from `AUDITING`.
- **Failed stop delivery -> `ATTN`, never `CHAT`.** Local intent stays
  authoritative (A3 stays `OFF`), `a3OperatorStopPending` carries the actionable
  reason, and the stop is retried boundedly and idempotently from the managed
  worker poll. A reload before the acknowledgement resumes it; a reload after it
  neither resurrects A3 nor re-delivers.
- **Internal disarms never touch the Bridge.** `setAutoAuditEnabled(false,
  { operator: false })` — route hydration drift, runtime migration, storage
  repair, worker stand-down, stale conversation-key repair, managed recovery —
  stays local and stays repairable. Only a human decision retires a managed run.
- **Multi-worker isolation.** Each worker owns only its own dispatch, no
  cross-tab adoption, and one operator stop affects only its own lane while the
  other workers keep running.

### Operator step (NOT yet performed)

The real-browser run below has **not** happened. It requires a live operator
session and is deliberately left unclaimed rather than inferred from synthetic
evidence.

1. Start a FastPrompter A3 campaign and reach Bridge `AUDIT 0/3` /
   `worker Chrome #1`.
2. **Accidental split-brain:** reload / rehydrate until the local runtime
   reconstructs. Required: A3 returns `ON` on its own, the compact label is
   never `CHAT`, the wave identity is preserved, no duplicate Core, campaign
   continues.
3. **Interrupted response:** stop the current Core once. Required: wave stays
   0/3, no `DONE`, no `CHAT`, paused/attention visible, no duplicate Core. Reload
   and confirm the same managed interrupted state reconstructs.
4. **Explicit human OFF:** on a second managed campaign, uncheck A3 by hand.
   Required: A3 stays `OFF`, no auto re-arm, Bridge receives the canonical
   operator stop, Project Room stops showing ordinary active `AUDIT` ownership,
   the lane is not permanently occupied, reload does not resurrect it.
5. **Three-worker smoke:** repeat ownership recovery with at least three
   workers; prove per-worker ownership, no cross-tab adoption, and that one
   explicit stop affects only its own lane.

## Generation truth: a finished answer is never BUSY (Widget 0.0.85)

Install the served build through the supported path (sections 1-2 above). The
served build is 0.0.85,
`sha256 1b89ffaf2179dcba0d392615176e12600b822288714bb6a5252bad0107303ac1`.

The production symptom: an enabled A3 runtime sat at BUSY with a visibly
FINISHED FastPrompter Core (final response actions mounted, "Worked for 13m 50s",
no real generation Stop on screen) and the campaign stayed at 0/3 forever. This
was never only a label: the same false positive short-circuited
`evaluateAutoAudit()` before `completedAssistantCandidate()`, so no SAVE, no
wave commit and no next wave could happen.

Two independent defects produced the false positive, and BOTH had to be closed:

1. `CHATGPT_STOP_SELECTOR` carried the wildcard `button[data-testid*="stop" i]`
   and a bare `button[aria-label="Stop"]`.
2. The match was admitted by `chatGPTSendNearComposer()` — a Send-DISCOVERY
   predicate whose 7-level ancestor walk above the prompt editor accepts almost
   any visible element in the bottom page shell. Identity alone and proximity
   alone are both insufficient, so the widget now requires exact canonical
   identity AND proven ownership of the current composer.

### Machine-proven (synthetic regression surface)

```bash
node --test tests/widget/w7-008-generation-truth.test.js
node --test tests/widget/w7-003-live-generation-state.test.js
node --test tests/widget/w7-004-hydration-miss-recovery.test.js
node --test tests/widget/w5-001-managed-a3-ownership.test.js
python -m pytest -q tests/test_browser_generation_truth_integration.py
python -m pytest -q tests/test_widget_release_identity.py tests/test_bridge_widget_delivery.py
```

`tests/widget/w7-008-generation-truth.test.js` is red-controlled against the
shipped 0.0.84 bytes: with the old userscript in place the headline case fails,
and it passes only with the fix. It covers the whole truth contract — canonical
Stop in the composer, canonical Stop in the composer action shell, an unrelated
page Stop, a `data-testid` containing "stop" that is not generation, a voice
control, response-action chrome, a completed answer, a completed answer beside a
stale stop-shaped control, the bounded stabilization overlap resolving each way,
the contradiction timeout, an interrupted ("Stopped thinking") answer, ordinary
chat regression, and a finished Core that actually commits its wave and sends
Wave 2 exactly once.

### Operator step (NOT yet performed)

**The real-browser half has NOT happened and is deliberately left unclaimed.**
The fix removes the defect class; only a live session can confirm that the
current chatgpt.com build exposes its generation control under one of the three
canonical identities, and that a finished Core in a real FastPrompter campaign
advances on its own.

1. Capture the live evidence first. From the repository root, in the browser
   profile that hosts the widget:

   ```bash
   python scripts/probe_chatgpt_generation.py --watch 900 5
   ```

   Leave it sampling for the whole Core, so one run records both phases. It
   dumps structure only — shape, identity and structural relation, never
   conversation text, prompts, account data or tokens.
2. While the model is actively thinking, `generating` must be `true` and
   `canonical_stop` must be populated. Record its real `data_testid` /
   `aria_label` / `composer_distance`.
3. When the model visibly finishes, within the bounded stabilization window
   `generating` must become `false`, the compact widget must NOT read `BUSY`,
   and the finished Core must be processed: 0/3 -> Core accepted/saved -> next
   canonical state -> Wave 2 begins. No manual page click, no toggling A3, no
   reload. Repeat once for Wave 2, then repeat the whole thing on a second
   project.
4. If `canonical_stop` is `null` while the model is visibly generating, the
   current build uses a generation identity outside the three canonical
   markers. Do NOT add a wildcard for it: record the real element, add that
   exact marker, and re-run step 1. If the contradiction persists instead, the
   widget raises `generation_truth_conflict` and shows `ATTN` with a written
   reason — that is the real failure state, and it sends nothing.

## Related: managed OpenCode launch smoke (T-196 Target I) the managed OpenCode launch repaired (architecture proof, no
`CANONICAL_RUNTIME_SOURCE_UNPROVEN`, alive > 10 s). That claim is historical
evidence, so T-196 re-runs the machine-checkable half:

```bash
python -m pytest -q tests/ui_qt/test_opencode_startup_liveness.py tests/test_opencode_launch_policy.py tests/ui_qt/test_launcher_focus_reuse.py
```

The remaining step is one operator click: Project Room -> **OpenCode** on a real
project, confirming no architecture-proof error, a live window after 10 seconds,
the correct bound project, and an active guard. If the
`canonical source root fails architecture proof` error returns, T-195 is
reopened or linked immediately.

