# Phase: SCOUT (mandatory before BUILD)

0. **Claim the ticket**: If you haven't already, move the top workable ticket from `## TODO` to `## DOING`, change its checkbox to `[/]`, and set your `owner:` and `claim_time:` fields on it (RFC § 1.4).
1. KNOWLEDGE/ first -- already know this? Skip re-reading. Does not exist? Skip, no overhead.
2. Ticket's files + ONE similar neighbor.
3. Note: naming, error style, imports, utils, harness, build commands.
   **The harness and build commands go into `KNOWLEDGE/` the first time
   this project needs them, and are cited afterwards rather than
   rediscovered.** They are durable truth by § 1.2's own definition, and
   a command each session re-derives is a command two sessions can
   disagree about while both believe they ran the check. Sources, in
   order: an existing `KNOWLEDGE/` entry, then Taskfile/Makefile/package
   scripts/project manifest/CI config. Ambiguous -> `WAIT: blocked`
   naming the missing command, never the most convenient guess.
4. The repo has an architecture -- find it, never invent a parallel one.
5. Durable finding -> KNOWLEDGE/. Grep before read -- scope grep to the ticket's files and one neighbor, not the whole repo.
6. LOG exactly one Event Graph line summarizing the scope: `- DATE [E-###] [parent: E-###] [T-###] RUN: SCOUT -- <findings, one line>`.
7. Checkpoint: write `BOARD.md` then `STATE.md` in that order (RFC § 1.5).

After SCOUT: STATE -> BUILD.