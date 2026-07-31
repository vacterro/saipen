# saipen BOOT -- cold-start kernel

You are continuing a project whose entire brain persists in `.saipen/`.
This file is the only document a normal continue needs. It gives the
execution order and nothing else: no rule is *defined* here, so nothing here
can drift out of sync with `RFC.md`, which decides every question this file
does not answer.

## Fast path

1. **Bind `project_root`, then read its `.saipen/STATE.md`.** An explicit
   project-root target wins. Otherwise use `git rev-parse --show-toplevel`
   plus `git rev-parse --git-common-dir`; a common directory ending in
   `/.git` binds a linked worktree to that main worktree's root and shared
   gitignored `.saipen/`. Outside Git, use the nearest ancestor already
   carrying `.saipen/`. This binds location only: missing `STATE.md` there is
   corruption for step 2 to diagnose, not evidence that the cwd is unowned.
   Nothing owns the cwd? Refuse to guess or
   create a relative `.saipen/`; only `saipen set` after INIT confirms genuine
   absence. Keep the resolved absolute root for the session: every later
   checkpoint path is `<project_root>/.saipen/...`, even after `cd`. An
   explicit new root may deliberately retarget the session; an accidental cwd
   change may not. `saipen_home` points to the protocol install, not this root
   (RFC § 1.1).

2. **Validate STATE before executing anything in it.**
   Every field RFC § 1.2's required set names must be present and non-empty
   (read the set there -- this file deliberately does not copy it), including
   its fresh-INIT exception for `transition_from`: a brand-new INIT state
   legitimately has no previous phase to name, so its absence there is not
   damage to repair. Any
   missing, or STATE contradicted by `LOG.md`/`BOARD.md` -> RECOVER per
   RFC § 1.5 first. Do NOT execute `next_action` from an unrepaired state
   (RFC § 1.11, priority 1).
   `schema_version` absent or `1` is readable legacy, not a reason to recover
   before continuing: WARN, then upgrade at the next checkpoint. Any present
   `last_event` is still checked. At schema v2, an event-bearing LOG requires
   the marker to equal its highest `E-###`; absence or mismatch is
   contradiction and enters Recovery. A fresh empty LOG has no marker.

3. **Read `.saipen/BOARD.md`, then the active tail of `.saipen/LOG.md`.**
   Older history is sealed in `.saipen/logs/LOG-NNN.md`; load it only when a
   `parent:` chain or an audit walks back into it. The `last_event` freshness
   check needs only the newest event: use the active LOG tail when it has one,
   otherwise read the tail of the newest sealed segment. Do not scan every
   segment merely to rediscover the maximum.

4. **Distrust your own memory.** `STATE.agent` is not you, or `STATE.updated`
   is newer than your last write -> everything you remember about this project
   is stale by definition. The files win (RFC § 1.1).

5. **`human_note:` set?** Apply it this session, clear it, and LOG the trace in
   the same checkpoint: `DEC: applied human_note: <text>`, or
   `DEC: human_note -> T-###` if it became a ticket. One-shot, not standing law.

6. **Execute `STATE.next_action` immediately.** That value IS the instruction;
   do not ask "what should I do?" (`CONFORMANCE.md` TEST-001). A `WAIT:` means
   output that question verbatim and stop. If `next_action` is absent, vague,
   or fails § 1.2's prefix/category checks, it is corrupt -- RECOVER (step 2),
   do not improvise a replacement. When you must choose what to do at all,
   RFC § 1.11's priority decides and is not a judgement call:
   RECOVER > UNBLOCK > FINISH > START > MAINTAIN. Its five legal
   forms and their arguments are defined in RFC § 1.2:
   `WAIT:` / `saipen <command>` / `PHASE <phase> [T-###]` / `RUN:` /
   `RESUME: T-### <phase>`.
   **"Immediately" never overrides RFC § 1.1's destructive-op gate.** A
   `next_action` that would force-push, drop a schema, rewrite history, or
   mass-delete files still needs explicit user confirmation -- a previous
   session writing it into `STATE.md` is not the user authorizing it.

7. **Load the phase doc only when you need its rules**, from
   `<saipen_home>/phases/<phase>.md`, one phase at a time.
   `saipen_home` empty or dead on this machine? Clone
   `github.com/vacterro/saipen` and update the field at your next checkpoint
   (RFC § 1.7). No git either -> set `phase: BLOCKED` and
   `next_action: WAIT: blocked -- saipen_home missing/dead and git
   unavailable; give me the path to a saipen/ clone on this machine, or
   install git`.

8. **Checkpoint after every ticket, after every phase transition, and before
   you stop** -- not per edit, not saved up for session end: LOG (append) ->
   `BOARD.md` -> `STATE.md`, that order (RFC § 1.5). Then **read back all
   three**: your LOG line is the file's last line, your BOARD changes are on
   the board, and `STATE.md` still carries § 1.2's required set. Where
   `tools/validate.py` runs it is the cheapest shape check, but it is not a
   substitute for the read-back -- an empty board passes every shape check
   ever written. A checkpoint you cannot resume from is not a checkpoint.
   The final STATE write uses `schema_version: 2` and `last_event: N`, where
   `E-N` is the highest event across sealed plus active LOG after step 1; omit
   it only for a fresh bootstrap whose LOG is still empty. Recovery writes the
   same pair from that evidence, including when upgrading legacy state.

## Anything else

- `saipen <word>` that is not a bare continue -- RFC § 1.10's command surface.
- Unrecognized word: check `.saipen/extensions/*/PROTOCOL.md` and `README.md`
  first (RFC § 1.9 -- a project extension may define it). Still nothing: list
  the recognized commands and stop. Never guess.
- Rule questions `STATE`/`BOARD`/`LOG` + the active phase doc don't answer:
  `saipen/RFC.md` (constitution, authoritative on everything),
  `saipen/STYLE.md` (chat voice), `saipen/UI.md` (UI work only).
- **`agent:` is inherited, not invented**: keep the value `STATE.md` already
  carries. It names the seat, not your model build -- § 1.4's concurrency
  test compares it against itself, and six invented names in one project is
  what happens otherwise. Genuinely a different actor? Change it and LOG a
  `DEC` naming both.
- **Reply language, before any output**: the language the user themselves
  typed. No prose from them yet (a bare command)? **English.** Never inferred
  from the OS/IDE locale, the platform UI, or the files in the repository --
  this one ships 33 translated guides, and a session answered a Russian
  speaker in Ukrainian for no other reason. Full rule in `saipen/STYLE.md` and `RFC.md`;
  it is repeated here because it governs the first token, so deferring it to
  a "rule question" is already too late.
- `CHANGELOG.md` is never part of a cold start.
