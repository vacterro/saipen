# FUTURE GATE — SAITELEMES AUTOMATIC AGENT TELEGRAMS

STATUS: PART 3 (TURN-ENTRY READ) IMPLEMENTED BY T-1497 / PARTS 1-2 (AUTOMATIC SEND)
NOT AUTHORIZED FOR IMPLEMENTATION

Update 2026-09-23: the operator authorized the first narrow slice (SAIPEN SRC-113).
`saipen continue`, `cc` and `status` JSON answers now carry a `telegrams` block:
unread COUNTS for the acting seat, read through
`saimail-local --json saipen telegrams --workspace <SAIMAIL_WORKSPACE> --scan-budget 200`
(header-only; nothing opened). It runs only when the per-machine carrier
`SAIMAIL_WORKSPACE` is set and `saimail-local` resolves on PATH; otherwise it reports
`NOT_CONFIGURED` or `UNAVAILABLE` and starts no process. Sender text never reaches the
route, arrival creates no Work, and a broken or slow SAIMAIL is a state, never a failed
`continue` (tools/saipen_engine/telegrams.py, tools/test_t1497_turn_entry_telegrams.py).
The automatic send trigger below remains unauthorized.
PRIORITY: P2 EFFICIENCY + MULTI-AGENT COORDINATION
OWNER: SAIPEN protocol (trigger and turn-entry read); SAIMAIL (transport, T-109)
SOURCE: operator order relayed from SAIMAIL session, seat `opus`, 2026-09-22
PROVENANCE: SAIMAIL project lineage-3172dbca95fc4945955bdee3acff8d75, HEAD 3fa8f22,
SAIMAIL receipts SRC-096 (T-108, DONE E-1381) and SRC-097 (T-109, DONE)

## Operator words (verbatim)

> SAITELEMES - это как телеграмма для другого работающего агента, это должно
> происходить автоматически пока выясняется текущий аудит чтобы решались задачи
> эффективнее.

> И это SAIPEN PROTOCOLIST тоже должен быть уже об этом уведомлённым и записанным
> в дело желательно.

Meaning: a SAITELEME is a short telegram from one running agent to another running
agent. When an agent's current audit or work turns up a fact that belongs to another
live agent's domain, the telegram goes out automatically while the audit is still
running, not after a human asks for it. The goal is fewer reconstruction round-trips.

## Observed evidence (this session)

1. **The finding waited for a human.** While building the SAIMAIL S2 seam (T-108), the
   SAIMAIL agent found three SAIPEN defects: silent actor inheritance, no CLI surface
   for explicit handover, and LOG time without a zone. The protocolist learned nothing
   until the operator typed "Дай САЙПЕН ПРОТОКОЛИСТУ телеграмму".
2. **The live channel is not automatic.** The cross-session host message to the running
   SAIPEN session was held for that session's user approval and expired unapproved. It
   was resent, and it is still subject to the same approval.
3. **The only channel that reached the protocolist without approval was a file drop:**
   `%LOCALAPPDATA%\saipen\protocol_incidents\inbox\SAI-DEFECT-20260922-silent-actor-inheritance-misattribution.md`.
   Nothing in SAIPEN's turn entry reads that inbox, so it waits for triage.

## Gap

SAIPEN has no notion of "another live agent should know this now". Findings about a
foreign domain end up in one of three places: the finder's own LOG (the foreign agent
never reads it), a human relay, or a cold inbox triaged later. There is no automatic
send at discovery time, and no bounded read at the recipient's turn entry.

## BOUNDED FOLLOW-UP OPTION

1. **Trigger (SAIPEN).** When a checkpoint, REVIEW finding or refusal names a defect
   whose owner is another live agent or project (the protocolist for protocol
   defects), the operation layer emits one telegram. The durable packet is the
   authority; the live nudge is best effort.
2. **Transport (SAIMAIL, T-109).** A telegram is one ordinary sealed SAIMAIL message.
   Its kind comes from the existing closed SENV2 set (`WARNING`, `DISCOVERY`,
   `PROTOCOL_PROPOSAL`, ...). There is **no** `TELEGRAM` kind and no sender
   importance field: SENV2 kinds are a closed wire set, and attention stays
   receiver-owned. TOPIC = the audit/Work id; body = one SAILANG record. When it cites
   SAIPEN evidence, it uses the S2 citation (`KIND:O`, `EV` = sha256 of the exact LOG
   line, re-derivable with `saimail-local saipen verify`). It is delivered into the
   recipient workspace's Post Office with no human relay and no network. (Correction
   of the first draft of this note, which named a `TELEGRAM` kind.)
3. **Turn-entry read (SAIPEN).** BOOT/`continue` performs one bounded, header-only
   unread check of the seat's workspace (`inbox --state UNREAD`, optionally by TOPIC) and surfaces the count. Opening stays
   explicit. A telegram is data and never becomes a command (SAIMAIL I1). It never
   creates Work by arriving; Work stays a human/Core decision.

## Required hostile controls

- A telegram whose body contains `saipen push`, `cc` or tool-call-looking text changes no
  route (I1 red control).
- A telegram can never transfer a claim, write BOARD/STATE, or skip a WAIT.
- A forged citation (right `EV`, lying `SUBJ`/`CLAIM`) fails `verify` (already a SAIMAIL
  regression test, D-057).
- Flooding: a declared per-recipient budget. Over budget the telegram is dropped to the
  durable packet only, and never retried in a loop.

## NON-GOALS

No network transport, no daemon, no auto-open, no auto-Work creation, no trust score for
senders, and no relaxation of foreign-live claim rules. Related:
[FUTURE GATE — VOLUNTARY MID-WORK CLAIM HANDOFF](FUTURE%20GATE%20%E2%80%94%20VOLUNTARY%20MID-WORK%20CLAIM%20HANDOFF.md)
is the handover defect #2 above already describes.

## ORIGINATING MISSION

SAIMAIL SRC-096 "Возведи и соедини с SAIPEN как нибудь" (T-108, S2 seam bridge, DONE),
followed by SRC-097 SAITELEMES (T-109, DONE: `saimail-local saipen telegram|telegrams`, `spec/26-SAITELEMES-v0.md`, D-058). SAIMAIL records: `spec/04-SAIPEN-SEAM.md`
"S2 as built", `spec/DECISIONS-D057.md`, `humbox/FUTURE-GATES-V6.md` §11.
