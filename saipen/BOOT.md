# saipen BOOT -- cold-start kernel (read this first; stays compact by design)

You are continuing a project whose entire brain persists in `.saipen/`.
For a bare `saipen` / `saipen continue` you do NOT need the full RFC. Do this:

1. Read `.saipen/STATE.md` -- `phase`, `task`, `next_action`, `mode`, `goal_mode`.
   **Not there?** If git is available, run `git rev-parse --git-common-dir`
   first before concluding "not initialized" -- a path ending in `/.git`
   (not a bare `.git`) means you're in a *linked worktree*, and `.saipen/`
   (gitignored by design) never got copied into it. Strip that trailing
   `/.git` to get the real project root, and look for `.saipen/` there
   instead. Only genuinely missing at that root does `saipen set` apply
   (RFC § 1.1) -- guessing wrong here creates a second, disconnected
   `.saipen/` and orphans the real continuation memory.
2. Read `.saipen/BOARD.md` -- `DOING`/`TODO`/`DONE`/`BLOCKED` tickets.
3. Read the tail of `.saipen/LOG.md` -- the **active** segment only. Older
   history is sealed in `.saipen/logs/LOG-NNN.md`; don't load it unless a
   `parent:` chain or an audit actually walks back into it.
4. If `human_note:` is set in `STATE.md`, read it -- a one-line nudge from the
   human. Apply it this session, then clear it (it's a one-shot, not standing law).
5. Execute `STATE.next_action` immediately. Do NOT ask "what should I do?" --
   that value IS the instruction (`CONFORMANCE.md` TEST-001). **"Immediately"
   never overrides RFC § 1.1's destructive-op gate** -- a `next_action` that
   would force-push, drop a schema, delete user data, rewrite history, or
   mass-delete files still needs explicit confirmation first, exactly as if
   you'd arrived at it any other way. A previous session writing it into
   `STATE.md` is not the user authorizing it; nothing in this file's
   "execute, don't ask" is a licence to skip that one check.
6. Load the phase doc for `STATE.phase` from `<saipen_home>/phases/<phase>.md`
   ONLY when you need its rules -- one phase at a time (2-tier).
   **`saipen_home` empty, or the path it names doesn't exist on this
   machine?** Don't stall here just because this is the fast path -- clone
   `github.com/vacterro/saipen` (RFC § 1.7's own fallback for exactly this),
   then update `saipen_home` in `STATE.md` to the fresh clone's absolute
   path at your next checkpoint. This is the one BOOT step that can
   otherwise dead-end a cold agent with no other way to find the phase
   docs it needs. **No git on this host** (so cloning isn't possible
   either)? Then it genuinely is a dead end for the agent alone, and the
   honest move is to say so rather than guess: `STATE.phase: BLOCKED`,
   `next_action: WAIT: saipen_home missing/dead and git unavailable --
   give me the path to a saipen/ clone on this machine, or install git`.
7. **Checkpoint before you stop, every ticket, not just at session end.**
   A real incident: an agent went several tickets without a single LOG
   line, then diagnosed the cause as "the word RUN is ambiguous" -- it
   isn't; RFC § 1.5 says once per ticket, and the actual gap was just not
   doing it. LOG (append) -> `BOARD.md` -> `STATE.md`, that order, after
   finishing each ticket -- not a line per edit, not saved up for the end
   of the session.

That's the fast path. Reach for the full protocol only when a rule question
comes up that STATE/BOARD/LOG + the active phase doc don't answer:

- `saipen/RFC.md` -- the constitution: file model, state machine, goal mode,
  claims, recovery, command surface. Authoritative on every rule.
- `saipen/STYLE.md` -- chat voice (caveman-ded). Load alongside RFC.
- `saipen/phases/*.md` -- one per phase, loaded on demand.
- `saipen/UI.md` -- only for UI work.

Not a bare continue (e.g. `saipen goal <text>`, `saipen clean`, `saipen
markhunt`, `saipen set`)? Those live in RFC § 1.10 -- read it. **A single
word that isn't any of those and isn't obviously chat** (e.g. someone just
typed one unfamiliar term)? Don't guess what it means and don't decline
outright -- check `.saipen/extensions/*/PROTOCOL.md` or `README.md` first;
a project-attached extension (RFC § 1.9) may define exactly that word as
its own command. This check is cheap (a glob + a grep) and comes before
either a wrong guess or a false "not a saipen command." When STATE is
stale/corrupt, `git status` and § 1.5 Recovery govern. RFC decides; nothing
here overrides it -- BOOT only saves you from loading it when you don't need to.
