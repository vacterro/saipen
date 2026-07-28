# saipen BOOT -- cold-start kernel

You are continuing a project whose entire brain persists in `.saipen/`.
This file is the only document a normal continue needs. It gives the
execution order and nothing else: no rule is *defined* here, so nothing here
can drift out of sync with `RFC.md`, which decides every question this file
does not answer.

## Fast path

1. **Read `.saipen/STATE.md`.**
   Missing, and git is available? Run `git rev-parse --git-common-dir` before
   concluding "not initialized". Output ending in `/.git` means you are in a
   linked worktree, which never receives the gitignored `.saipen/` -- strip
   that suffix for the real project root and look there. Genuinely absent at
   *that* root -> `saipen set` (RFC § 1.1).

2. **Validate STATE before executing anything in it.**
   Every field RFC § 1.2's required set names must be present and non-empty
   (read the set there -- this file deliberately does not copy it). Any
   missing, or STATE contradicted by `LOG.md`/`BOARD.md` -> RECOVER per
   RFC § 1.5 first. Do NOT execute `next_action` from an unrepaired state
   (RFC § 1.11, priority 1).

3. **Read `.saipen/BOARD.md`, then the active tail of `.saipen/LOG.md`.**
   Older history is sealed in `.saipen/logs/LOG-NNN.md`; load it only when a
   `parent:` chain or an audit walks back into it.

4. **Distrust your own memory.** `STATE.agent` is not you, or `STATE.updated`
   is newer than your last write -> everything you remember about this project
   is stale by definition. The files win (RFC § 1.1).

5. **`human_note:` set?** Apply it this session, clear it, and LOG the trace in
   the same checkpoint: `DEC: applied human_note: <text>`, or
   `DEC: human_note -> T-###` if it became a ticket. One-shot, not standing law.

6. **Execute `STATE.next_action` immediately.** That value IS the instruction;
   do not ask "what should I do?" (`CONFORMANCE.md` TEST-001). Its five legal
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
   `next_action: WAIT: saipen_home missing/dead and git unavailable -- give me
   the path to a saipen/ clone on this machine, or install git`.

8. **Checkpoint after every ticket and before you stop** -- not per edit, not
   saved up for session end: LOG (append) -> `BOARD.md` -> `STATE.md`, that
   order (RFC § 1.5). Then re-read the `STATE.md` you just wrote and confirm
   the required fields survived. Where `tools/validate.py` runs, it IS that
   check. A checkpoint you cannot resume from is not a checkpoint.

## Anything else

- `saipen <word>` that is not a bare continue -- RFC § 1.10's command surface.
- Unrecognized word: check `.saipen/extensions/*/PROTOCOL.md` and `README.md`
  first (RFC § 1.9 -- a project extension may define it). Still nothing: list
  the recognized commands and stop. Never guess.
- Rule questions `STATE`/`BOARD`/`LOG` + the active phase doc don't answer:
  `saipen/RFC.md` (constitution, authoritative on everything),
  `saipen/STYLE.md` (chat voice), `saipen/UI.md` (UI work only).
- `CHANGELOG.md` is never part of a cold start.
