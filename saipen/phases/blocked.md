# Phase: BLOCKED

The whole session is stuck, not just one ticket -- you only land here after
confirming no other ticket on `BOARD.md` is workable (`phases/verify.md` or `phases/done.md`).

0. **LOG the block**: one Event Graph line `- DATE [E-###] [parent: E-###] [T-###] RUN: BLOCKED -> <blocker description>` before anything else — makes the blocking event auditable even if it gets unblocked later.
1. Check `blocker:` in STATE.md or recent LOG.md entries. Empty `blocker:`
   here is itself non-conformant (CORE.md §1.2) -- determine the real reason
   you're stuck and write it before proceeding.
2. Re-scan `BOARD.md` for any unblocked `TODO` once more -- if one exists,
   go work it instead of proceeding to step 3. This phase is the last resort.
3. Ask the user for clarification, credentials, or manual intervention:
   `next_action: WAIT: blocked -- <the specific question or what's needed>`
   (CORE.md §1.2's category vocabulary; `blocked` is the category for a
   session-level unblock request).
4. Do not spin or guess blindly. Wait for facts.
5. If the blocker is resolved by the user, tick BOARD if applicable, update STATE -> PLAN, SCOUT, or DONE (if the board is now empty).
