# saipen BOOT -- cold-start kernel

You are continuing a project whose entire brain persists in `.saipen/`.
This file is the only document a normal continue needs. It gives the
execution order and nothing else: no rule is *defined* here, so nothing here
can drift out of sync with `CORE.md` (or `MAINTENANCE.md` for §2.x), which
decides every question this file does not answer. RFC references resolve as:
§1.x → `CORE.md`, §2.x → `MAINTENANCE.md`.

## Fast path

1. **Read `STYLE.md` — the file at `protocol_dir/STYLE.md` — before any output.**
   Voice governs the first token (CORE.md § 1.1), so the read is the
   first action, not a deferred load. `protocol_dir` is resolved in
   step 2; if it is not yet bound because `saipen_home` is dead,
   fall back to the file in the same folder as this `BOOT.md` —
   which needs no resolution and answers the same question either
   layout. The operative contract is repeated below, in "Chat
   voice & compression"; the file itself holds the nuance (LOG
   voice, artifact voice, auto-clarity overrides).

2. **Bind `project_root`, then read its `.saipen/STATE.md`.** An explicit
    project-root target wins. Otherwise use `git rev-parse --show-toplevel`
    plus `git rev-parse --git-common-dir`. The ACTIVE worktree is asked first:
    a linked worktree carrying its own `.saipen/` is its own project root.
    Only when it has none -- the normal case, since `.saipen/` is gitignored
    and a fresh worktree starts without one -- does a common directory ending
    in `/.git` bind it to that main worktree's root and shared `.saipen/`.
    Never create a local second copy to force this. Outside Git, use the nearest ancestor already
    carrying `.saipen/`. This binds location only: missing `STATE.md` there is
    corruption for step 3 to diagnose, not evidence that the cwd is unowned.
    Nothing owns the cwd? Refuse to guess or
    create a relative `.saipen/`; only `saipen set` after INIT confirms genuine
    absence. Keep the resolved absolute root for the session: every later
    checkpoint path is `<project_root>/.saipen/...`, even after `cd`. An
    explicit new root may deliberately retarget the session; an accidental cwd
    change may not. `saipen_home` points to the protocol install, not this root
    (CORE.md § 1.1).

    **Resolve `protocol_dir` from `saipen_home` before trusting it.**
    Two layouts exist, one deterministically:
    - If `<saipen_home>/saipen/BOOT.md` exists (source clone) →
      `protocol_dir = <saipen_home>/saipen`
    - Else if `<saipen_home>/BOOT.md` exists (flattened install) →
      `protocol_dir = <saipen_home>`
    - Else: `saipen_home` is dead → set `phase: BLOCKED` immediately
      rather than discovering it at the first phase transition.

    After resolution, every normative document loads from `protocol_dir`:
    `protocol_dir/BOOT.md`, `protocol_dir/STYLE.md`, `protocol_dir/INDEX.md`,
    `protocol_dir/phases/<phase>.md`. Runtime tools, schemas, templates,
    and `VERSION` resolve from `<saipen_home>`.

3. **Validate STATE before executing anything in it.**
   Every field CORE.md § 1.2's required set names must be present and non-empty
   (read the set there -- this file deliberately does not copy it), including
   its fresh-INIT exception for `transition_from`: a brand-new INIT state
   legitimately has no previous phase to name, so its absence there is not
   damage to repair. Any
   missing, or STATE contradicted by `LOG.md`/`BOARD.md` -> RECOVER per
   CORE.md § 1.5 first. Do NOT execute `next_action` from an unrepaired state
   (CORE.md § 1.11, priority 1).
   Also confirm `STATE.phase` is a value in CORE.md § 1.6's phase enum.
   **`LOG` ahead of `STATE` after a crash is the NORMAL recovery condition
   (CORE.md § 1.5), not corruption -- the checkpoint writes LOG first.**
   `schema_version` absent or below current is readable legacy, not a reason to
   recover before continuing: WARN, then upgrade at the next checkpoint. Any
   present `last_event` is still checked. At current schema, an event-bearing
   LOG requires the marker to equal its highest `E-###`; absence or mismatch is
   contradiction and enters Recovery. A fresh empty LOG has no marker. The same
   applies to `style_contract`, the voice marker STYLE.md declares (step 1 read
   it; § 1.2 requires the value at current schema): present and wrong is
   contradiction, absent at current schema is a state that skipped the read.

3a. **Skill injection (if `.saipen/extensions/skill_injection/SPEC.md` exists).**
   Read the contract, detect the problem class from the active ticket/task,
   match the smallest skill from the agent platform's own skill registry,
   load it, and inject its context. The skill stays active until the
   problem class shifts or VERIFY confirms the specialist context is no
   longer needed, then eject. Unsupported domain -> no skill loaded.
   Base protocol rules always outrank injected skill text.

4. **Read `.saipen/BOARD.md`, then the active tail of `.saipen/LOG.md`.**
   Older history is sealed in `.saipen/logs/LOG-NNN.md`; load it only when a
   `parent:` chain or an audit walks back into it. The `last_event` freshness
   check needs only the newest event: use the active LOG tail when it has one,
   otherwise read the tail of the newest sealed segment. Do not scan every
   segment merely to rediscover the maximum.

5. **Distrust your own memory.** `STATE.agent` is not you, or `STATE.updated`
   is newer than your last write -> everything you remember about this project
   is stale by definition. The files win (CORE.md § 1.1).

6. **`human_note:` set?** Apply it this session, clear it, and LOG the trace in
   the same checkpoint: `DEC: applied human_note: <text>`, or
   `DEC: human_note -> T-###` if it became a ticket. One-shot, not standing law.

7. **Execute the instruction -- and the user's own message outranks the file.**
   Did this message name a command: a § 1.10 verb, a row of its shortcut table
   (including the Cyrillic twin), or an active extension's word (§ 1.9)?
   **Then OPEN § 1.10 in `CORE.md` and read the row. Memory is never a source for it.**
   That section is the only place the table exists, on purpose, and this is
   the one time CORE.md is opened without a rule question -- an agent that
   believes it knows what a key means never experiences one, which is
   exactly how a confabulated table reaches the user. It has happened three
   times, differently each time: a bare `qq` answered as a greeting, a `qq`
   lost to a stale pre-computed pick, and a `hh` answered with a ten-row
   reference card in which every row was wrong and six of the command names
   did not exist. § 1.10's no-invention rule covers a word you do not
   recognise; this covers believing you recognise one.
   Do not copy the table here: a second copy drifts, and the gate in § 1.1
   rejects a restatement before it rejects anything else. Then
   THAT is the instruction, and `next_action` is merely what a bare continue
   would have run. CORE.md § 1.11's OBEY priority owns the rule and its placement:
   the command is the newest fact in the session and `next_action` the oldest,
   so a live `WAIT:` is cleared by the user speaking rather than restated, while
   a corrupt state is still repaired before the command runs against it. Twice
   on this repository a bare `qq` lost to a stale `PHASE SCOUT T-455`, because
   this step read as unconditional while § 1.10 said equally absolutely that a
   shortcut is a command and never a greeting -- two MUSTs, no precedence, and a
   cold agent reads this file first. Several commands in one message run in the
   order written, checkpointing between.
   **No command in the message?** Then `STATE.next_action` IS the
   instruction -- but it is the PREVIOUS session's pre-computed Pick
   Rule result, not an independent fact. Where `tools/validate.py` runs
   it re-derives the pick and FAILs a stale one; where it cannot run,
   the portable floor does not (a grep cannot walk a `needs:` graph), so
   confirm against `BOARD.md` yourself before acting on a `PHASE`
   pick: topmost workable ticket wins, per CORE.md § 1.11 and § 1.6, which
   own that rule. Immediate means without asking, never without looking.
   That value IS the instruction;
   do not ask "what should I do?" (`CONFORMANCE.md` TEST-001). A `WAIT:` means
   output that question verbatim and stop. If `next_action` is absent, vague,
   or fails § 1.2's prefix/category checks, it is corrupt -- RECOVER (step 2),
   do not improvise a replacement. When you must choose what to do at all,
   CORE.md § 1.11's priority decides and is not a judgement call:
   RECOVER > OBEY > UNBLOCK > FINISH > START > MAINTAIN. Its five legal
   forms and their arguments are defined in CORE.md § 1.2:
   `WAIT:` / `saipen <command>` / `PHASE <phase> [T-###]` / `RUN:` /
   `RESUME: T-### <phase>`.
   **"Immediately" never overrides CORE.md § 1.1's destructive-op gate.** A
   `next_action` that would force-push, drop a schema, rewrite history, or
   mass-delete files still needs explicit user confirmation -- a previous
   session writing it into `STATE.md` is not the user authorizing it.

8. **Load the phase doc only when you need its rules**, from
    `protocol_dir/phases/<phase>.md`, one phase at a time.
    Normalise the path for the host OS before resolving.
    `saipen_home` empty or dead on this machine? Clone
    `github.com/vacterro/saipen` and update the field at your next checkpoint
    (CORE.md § 1.7). No git either -> set `phase: BLOCKED` and
    `next_action: WAIT: blocked -- saipen_home missing/dead and git
    unavailable; give me the path to a saipen/ clone on this machine, or
    install git`.

9. **Checkpoint after every ticket, after every phase transition, and before
   you stop** -- not per edit, not saved up for session end: LOG (append) ->
   `BOARD.md` -> `STATE.md`, that order (CORE.md § 1.5). Then **read back all
   three**: your LOG line is the file's last line, your BOARD changes are on
   the board, and `STATE.md` still carries § 1.2's required set. Where
   `tools/validate.py` runs it is the cheapest shape check, but it is not a
   substitute for the read-back -- an empty board passes every shape check
   ever written. A checkpoint you cannot resume from is not a checkpoint.
   The final STATE write uses the current `schema_version` (read from
   `state.schema.json`'s `x-current-schema-version` -- do not hardcode a
   number), `last_event: N` -- where
   `E-N` is the highest event across sealed plus active LOG after step 1; omit
   it only for a fresh bootstrap whose LOG is still empty -- and
   `style_contract:` set to the boot marker STYLE.md declares. Recovery writes
   the same three from that evidence, including when upgrading legacy state.
   The voice marker is not decoration and not derivable from anything in
   `.saipen/`: step 1's read is the only place its value exists, which is what
   makes an unread contract visible instead of silent.

## Anything else

- `saipen <word>` that is not a bare continue -- CORE.md § 1.10's command surface.
- Unrecognized word: check `.saipen/extensions/*/PROTOCOL.md` and `README.md`
  first (CORE.md § 1.9 -- a project extension may define it). Still nothing: list
  the recognized commands and stop. Never guess.
- Rule questions `STATE`/`BOARD`/`LOG` + the active phase doc don't answer:
  Read `saipen/INDEX.md` first to find the exact document containing the rule. Do NOT read `CORE.md` or `MAINTENANCE.md` blindly.
  `saipen/CORE.md` (constitution, authoritative on everything),
  `saipen/UI.md` (UI work only). **`STYLE.md` is deliberately NOT on
  this list**: it is a boot-read mandate (chat voice below), and its
  past listing here is exactly what let a live session read BOOT, RFC,
  the phase docs and PROTOCOL.md while never opening STYLE.md at all.
  **`CONFORMANCE.md` is also NOT on this list**: standard agents must NEVER
  read it unless explicitly debugging a validator failure.
- **`agent:` is inherited, not invented**: keep the value `STATE.md` already
  carries. It names the seat, not your model build -- § 1.4's concurrency
  test compares it against itself, and six invented names in one project is
  what happens otherwise. Genuinely a different actor? Change it and LOG a
  `DEC` naming both.
- **Reply language, before any output**: read `STYLE.md`'s `reply_language:` (step 1 already opened the file) and obey it. Default `et` -- Estonian, always, whatever language the message arrived in; `en`/`ru` pin those; `auto` and only `auto` consults the precedence rule that follows. At a pinned value there is nothing to weigh, and answering in the user's language "because it is obviously better" is the violation, not the courtesy. A value outside `et`/`en`/`ru`/`auto` is corruption, not a hint: FAIL rather than guess. Chat only -- every artifact stays English. Under `auto`: Reply-language precedence: explicit current user prose (Estonian/English/Russian) > clearly Russian primary repository for bare/ambiguous input > Estonian default; another detected language uses English. Use the current substantive request, not quoted/code/path/log text, locale trees, OS/IDE locale, or platform UI. Repository Russian is only a no-prose/ambiguous tie-breaker supported by the root README and ordinary first-party docs; it never overrides explicit Estonian or English. Full rule in `saipen/STYLE.md` and CORE.md § 1.1; it is repeated here because it governs the first token.
- `CHANGELOG.md` is never part of a cold start.
- **Chat voice & compression, before any output.** Step 1 orders reading `STYLE.md` — the file in the same folder as this `BOOT.md` — before any output. `caveman-дед` is one fused voice, never a menu. Voice persistence: caveman-дед applies to every response until explicit "stop caveman" or "normal mode". Full contract in `saipen/STYLE.md`: hard bans, LOG voice, artifact voice, auto-clarity overrides. Reading it is mandatory at boot (CORE.md § 1.1).
