# DRIFT_MATRIX — SAIHANDOFF 2026-11-18 SAIPEN × ZAICODE AGENT_DRIFT_REPAIR

- Work: T-2087 (SRC-421, admitted 2026-11-17T23:05:51Z); original operator
  bytes preserved as SRC-422 (sha256 0600cee65ae041b6..., 422048 bytes,
  witness model_supplied — this seat could not compare them with what the
  operator wrote; the file `V:/___VAC/_PIC/_Clipboard_stuff/
  SAIHANDOFF_SAIPEN_×_ZAICODE_AGENT_DRIFT_REPAIR_20261118_010249_0600cee6.md`
  is the physical source). Variant `..._001225_07997f56.md` differs by exactly
  11 U+00A0→U+0020 normalizations (measured), same mission text.
- Evidence snapshot rule: every row below was re-measured from the LIVE
  ZAICODE database `C:/Users/vac34/.zcode/cli/db/db.sqlite` (session
  sess_a3345396-c502-4aa7-8536-eff7baf6d8cb: 7081 messages / 23509 parts)
  and the live _BZDECOMP `.saipen` memory, not from the handoff's own prose.
  The capture markdown (41 MB) itself was NOT re-read beyond anchor
  verification; copy-time/historical uncertainty is flagged per row.

## Provenance matrix (measured now)

| surface | resolved path | identity | state |
| --- | --- | --- | --- |
| SAIPEN installed home | `C:/Users/vac34/AppData/Local/saipen/scheduled-source` | 8.1.0, engine digest sha256:d64ee12e... (BLOCKED.md measurement) | loaded (STATE.saipen_home) |
| SAIPEN source repo | this worktree, HEAD dc39709c0 | 8.1.1, engine digest sha256:37dbbc7a... | on-disk, unpublished |
| ZAICODE host db | `C:/Users/vac34/.zcode/cli/db/db.sqlite` | session row time_created 2026-11-09 22:23:05Z, title "PHASE BUILD T-924" | live, readable |
| _BZDECOMP project memory | `V:/___VAC/__K/__CODE/_MISC/_BZDECOMP/.saipen` | BOARD/LOG/intake live | live |

SOURCE_RUNTIME_MISMATCH stands (repo 8.1.1 vs installed 8.1.0); this
measurement session binds to the installed generation for all canonical
writes, per the T-2058 gate.

## E1 — ingress provenance: real_user → model_supplied

**Class: CONFIRMED_DRIFT (authority loss at SAIPEN intake; by-design
mechanism, wrong carrier).** Severity P1 (measured), not P0: the request
did reach work, but only as model-supplied witness.

Measured chain (all timestamps UTC, from db):

1. 2026-11-17T21:23:55.824Z — real user message
   `msg_mwl79i9a_6ed7c258-a680-4bd1-8446-06159c4cf77b`, exact text
   «И еще, killfeed снова выдаёт пустые пространства чёрные.»
   `metadata.inputProvenance = {origin: real_user, source: queue_promotion,
   humanAuthored: true, originalUserIntentId: 01a1e986-40bc-...}` — the
   trusted envelope EXISTS in the host DB.
2. 2026-11-17T21:24:14Z (LOG E-12361, 21:24) — agent tool call
   `call_066b600cd599442fa8f6ec14` ran
   `saipen start 'killfeed again renders empty black boxes in game (operator
   screenshot, top-right feed area); find regression and fix' --json` →
   receipt SRC-801 → T-919, `ingress_authority.witness = model_supplied`,
   `user_explicit = false`.
3. Stored SRC-801 body (archive) holds ONLY the English agent paraphrase;
   the Russian operator bytes and the screenshot reference exist in no
   SAIPEN receipt.

Prosecutor: a real_user/humanAuthored=true message became a
model_supplied ticket 19 seconds later; original bytes never crossed the
seam. Defender: ZAICODE→SAIPEN has NO registered transport on this host
(T-2060/T-2061 WAIT_USER; HOST_DISPATCH_UNAVAILABLE measurements);
`saipen start` cannot mint user_explicit authority it was not given, and
SRC-801's meta truthfully declares model_supplied. Verdict: the intake
half is fail-honest; the drift is the MISSING BRIDGE (host queue →
SAIPEN envelope), not a forged witness. Owning surface: ZAICODE host
transport + SAIPEN ingress contract (P0-A in the handoff).
Owner on this BOARD: T-2060/T-2061 (WAIT_USER_DECISION — need a genuine
authenticated native operator_carrier cc; this SAIPEN cc cannot renew it).

## E2 — priority & continuation: user message durability vs cc all

**Class: CONFIRMED_DRIFT (admission latency + verbatim loss, measured).**
Severity P1.

Measured window (db): user msgs `msg_mwl7qcgg_88b8ef3c...` 21:37:35.672Z
«Пока что не вижу еще нововведения в текущей сборке.» and
`msg_mwl7r40x_f5d12f3f...` 21:37:56.277Z «Про pocket service pod где еще
с утра жду про cooldown.» (both real_user, humanAuthored=true) were
followed at 21:37:56.993Z by assistant `msg_mwl7rkdl` →
`saipen continue --json | head -120` → PHASE SCOUT T-919 (E1's ticket),
i.e. synthetic continuation proceeded on the OLD ticket while two new
user requirements sat unadmitted.

Durable disposition happened only after the operator REPEATED the
requirements in new messages at 22:24:07Z («Да, работает, вижу. Давай
чуть переделаем...»), 22:25:38Z («...Service pocket pods снова не
пополняются...»), 22:27:48Z («Здесь слово Scrap... пересекается с HUD»),
22:32:52Z («Ну и "Scrap"... нажатие на Q ничего не делает»), yielding
SRC-802/T-920 (22:24:16Z), SRC-803/T-921 (22:31:31Z), SRC-804/T-922
(22:31:34Z), SRC-805/T-923 (22:33:00Z) — 47–55 minutes after the
original 21:37 asks, and each stored body is again an English agent
paraphrase, not the operator's verbatim bytes.

Prosecutor: fresh user intake was not promptly persistent; admissionSeq
ordering let unrelated cc-continuation keep the seat. Defender: within
ZAICODE the messages were never lost (queue_promotion, ordered ids
intact); no SAIPEN mechanism existed to pull them in real time (same
missing transport as E1); once the operator's repeat arrived, every
requirement became a durable ticket and T-919 was NOT falsely closed on
the way. Verdict: CONFIRMED drift at the seam (latency + paraphrase),
with honest durability once ingress existed. Owner: same E1 bridge;
the cc-all-vs-current-request precedence rule already exists in CORE
(current-request precedence; PICK-01) and was not violated inside
SAIPEN itself.

## E3 — test ≠ delivered

**Class: INSUFFICIENT_EVIDENCE (live byte-chain not measured this
session).** What IS measured: T-918 (15 s hit block/HUD) and T-919
(killfeed) sit on the _BZDECOMP BOARD as DONE, closure_mode own_patch,
publication_state pending; the _BZDECOMP tree has staged dist/workshop
surfaces. The user's live-game report contradicts DONE, but this session
did not measure the dist→package→workshop-install→game-loaded DLL chain
(no hash walk executed), so no verdict. The SAIPEN-side rule gap the
handoff names (no BUILT_NOT_DEPLOYED / DEPLOYED_NOT_VERIFIED delivery
state) is real and matches the repo's own publication_state vocabulary
already in use. No game code was touched (handoff constraint honored).

## E4 — response enforcement gap

**Class: HOST_ENV_LIMITATION (measured; correction over the handoff's
claim).** The first real command `msg_mw9tuskk_adf732c1...`
(2026-11-09T22:23:17.034Z, `/goal cc all`) carries
`metadata.inputIntent.responseContract` IN THE RAW HOST RECORD (found at
that exact JSON path; my earlier draft said the key was absent — that was
wrong and is corrected here). Measured values:
`replyLanguage: null`, `replyLanguageDeclarations: []`,
`enforcement {language: none, structure: none}`, `admissionMode:
"observed"`, and the host's own truthful limitation string
"response contract observed, not enforced: no reply_language is pinned;
the host does not verify the reply against EXEC-HUSH-01,
EXEC-RESPONSE-01". So the capture export faithfully reproduced a real
runtime contract; the drift is that the contract is ADVISORY-only while
STYLE.md pins reply_language et — no mechanical per-turn guard exists on
this host (T-1548 EXEC_RESPONSE_HOST_GAP owns the runtime binding).
No "prevented" claim made.

## E5 — truncated authority

**Class: CONFIRMED_DRIFT (host-side habit; measured population).**
`call_40ea86950e424d179f32935b` = `saipen continue --json 2>&1 | head
-120` (part part_mwl7scon_...) and `call_209fb0b6f3d94d95a6e7718e` =
`grep ... ../.saipen/BOARD.md | head-20` (part part_mwl7aiyw...).
Population measured: 25 `saipen continue` calls piped through head in
this session; 919 head-piped command lines overall; 148 grep-on-BOARD
calls. None of today's routing decisions in THIS seat used truncated
output (canonical entry consumed full JSON; T-2081's probes and
E-21439 diagnosis used full receipts). Verdict: historical drift real;
the SAIPEN-side hardening (full-JSON consumption, schema/EOF
validation) is already the repo's canonical route — T-1449/crew
convergence depend on it. Remaining gap: no mechanical guard rejects a
head-truncated saipen JSON before decisions; candidates for a future
bounded ticket.

## E6 — cancellation, metrics & compaction

**Class: INSUFFICIENT_EVIDENCE / partial HOST_ENV_LIMITATION.**
Measured: assistant `msg_mwl79z4i_d7d613ee...` (21:24:17.298Z) carries
`error` in the raw message (the AiSdkModelAdapterError/
model_request_cancelled family) — cancellation events are real host
records, not compaction artifacts. Compaction boundaries measured: three
"continued from a previous conversation" summaries (21:30, 21:43,
22:15/22:31) each re-inject prior tool calls as user-role parts —
hence message counts differ across scopes; the handoff's 6698/22228 vs
db 7081/23509 is export-format vs live-db difference, NOT proven
durable-state drift. Turn/session/target token attribution and
duplicate-source-intake were NOT instrumented this session; no verdict.
No stale-TODO closure was performed from historical counts (today's
decisions used live BOARD reads).

## E7 — bounded human action

**Class: AUTHORIZED_EXCEPTION (declined attempt, correctly bounded).**
`a87b87f1-8e44-4cc2-bd01-78a0223b46bb` = AskUserQuestion tool part
part_mwhap9pe_96bc3dc0... with `state.status = "error"` (host declined
the question mid-run). No fake human reply was recorded; no Steam
popup was clicked by the agent; no foreign process was stopped by this
work. The handoff's own classification (attempt/host refusal, not a
delivered human blocker) matches the raw state.

## Cross-cutting verdicts

- P0-A (trusted ingress) and P0-B (generation binding) both remain
  blocked on OPERATOR acts already recorded: the authenticated ZAICODE
  native operator_carrier cc (T-2060/T-2061) and the 8.1.1 generation
  install authorization (T-2058 BLOCKED.md routes 1–3). This session
  adds measured evidence (the host DB holds the real_user envelopes with
  sourceCommandId/queueItemId/clientId intact — the bytes the future
  bridge must carry verbatim), but cannot mint the transport.
- No fabricated PASS: nothing above claims DONE for any E-row beyond
  what a canonical receipt shows; T-919 etc. are the _BZDECOMP
  project's own rows, untouched by this seat.

## Honest limits of this measurement

1. Capture markdown itself not re-hashed end-to-end beyond the two
   variant files (11 NBSP diffs, mission text identical).
2. E3 byte-chain and E6 attribution need instrumented runs; not done.
3. All SAIPEN-side writes today went through the installed 8.1.0 CLI;
   the 8.1.1 repo generation stays unpublished (T-2058).
