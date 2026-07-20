# Phase: DONE

There is no more work to do on the current ticket.

1. **Check `goal_mode` in STATE.md FIRST, before anything else below.**
   `goal_mode: true` means you arrived here on your own mid-run, not
   because the user typed anything -- item 3's trigger ("user simply typed
   `/saipen`") does NOT apply to you. Per RFC § 2.4, a clean board is a
   waypoint, never a stop: proceed immediately to `HUNT`. Do NOT write
   `next_action: wait for user command` while `goal_mode: true` -- that
   value is only ever correct when `goal_mode: false`.
2. If the user wants to start a new project or big feature, run `saipen goal` (sets phase to PLAN).
3. If there are unresolved bugs, run `saipen SYMPTOM` (bare invocation -- there is no separate `fix` subcommand, see RFC § 2.4).
4. If the board is clear and the user simply typed `/saipen`, you MUST immediately run `saipen (hunt)` (sets phase to HUNT) to look for bugs.
5. If the user asks to add new features or brainstorm, run `saipen (add)` (sets phase to ADD).
