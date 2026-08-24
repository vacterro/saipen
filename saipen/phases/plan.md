# Phase: PLAN

Amplify user intent into tickets. <=8 lines of analysis: edge cases,
callers, migrations, UI states. Safe defaults over interrogation.

**With text (`saipen plan <text>`, `dd <text>`):** the text IS the work. Every item the user named becomes a ticket, inserted at the FRONT of `## TODO` -- board order is priority (CORE.md §1.6), so putting the request behind existing work answers it politely and never. Reword each item into something a cold agent can execute while the human still recognises what they asked for: state the defect or the goal, and where a one-line ask hides a failure mode, spell that out -- the user's phrasing carries intent, not ticket text. MUST NOT substitute the Proposal Mode below: four inventions in place of one instruction is the failure this paragraph exists to prevent. Spotted something the user missed? Ticket it BELOW theirs.

**Bare / Proposal Mode (`saipen plan` with no prompt):**
If `PLAN` is triggered without a specific user prompt (bare `saipen plan`), the agent MUST evaluate the codebase, existing `KNOWLEDGE/`, and git log to generate an autonomous proposal plan:
1. Identify logical next workflow steps (§ 2.3 Industrial Completion Rule).
2. Identify missing capabilities, refactoring, or architectural strengthening (§ 2.2 Evolutionary ADD).
3. Populate `BOARD.md` with structured proposal tickets.
4. Transition `STATE.phase` to `DONE` and halt for the user to choose. **The halt is a `WAIT:` whose category is `user brake`.** That category is the whole normative part -- it is what `tools/validate.py` matches and what § 1.11's UNBLOCK priority reads -- and the reason clause after it is yours to word for the human. Example, not a mandated string: `next_action: WAIT: user brake -- proposal plan is on the board, pick a ticket or say continue to take the top one`. **It is a `WAIT:` on purpose.** This step used to forbid a `WAIT:` "because it violates CORE.md §1.2", which is false in this exact state: § 1.2 restricts `WAIT:` to three fixed forms only at `DONE` with an EMPTY `## TODO`, and Proposal Mode has just filled `## TODO`, so a concrete user brake there is ordinary and legal. What the prohibition left behind was a halt with no legal expression at all -- the other four prefixes (`saipen `, `PHASE `, `RUN:`, `RESUME:`) each mean "do this now", so writing one and not executing it records an action the agent is forbidden to perform, and § 1.2 requires the value to be immediately executable. **There is no parked `PHASE`** -- a cold agent reading `PHASE SCOUT T-###` executes it, which is the whole point of the field. MUST NOT proceed to `SCOUT` on your own. The user's next command supersedes this brake per § 1.11's OBEY priority -- a bare `saipen` / `saipen continue` takes the topmost workable `## TODO` ticket and transitions to `SCOUT`, which is the default behavior, and naming a specific ticket picks that one instead.

Ticket shape: one goal, independently verifiable, `needs:` for deps.
Every ticket SHOULD carry `| verify: <command or criterion>` (CORE.md §1.2)
when known -- pin down how it'll be checked while the goal is still
fresh, not as an afterthought during VERIFY.
Board order = execution order. >10 tickets: waves, detail current only.

**Size gate:** <=2 files + obvious change? Skip detailed PLAN analysis
only -- BUILD -> VERIFY -> REVIEW -> SHIP -> DONE still all apply exactly
as normal, no correctness gate skipped for being small. LOG the size-gate
decision. STATE -> SCOUT or BUILD per the normal phase docs, never
straight to DONE.

**After PLAN (if not in Proposal Mode):** STATE -> SCOUT for first ticket.
If `execution_intent: goal` (MAINTENANCE.md §2.4): do not pause here -- proceed straight into
SCOUT. Also increment `goal_waves` by 1 (this PLAN run = a new wave), write the LOG line MAINTENANCE.md §2.4 requires for it -- `DEC: goal_waves N->M`, that exact text after the taxonomy, because § 1.5's Recovery rebuilds the counters by counting those lines and cannot find a bump that only ever reached `STATE.md` -- and
checkpoint STATE -- **except** when this PLAN was entered directly from
`ADD`'s `RETURN PLAN` (`phases/add.md`): that `HUNT`->`ADD` cycle's wave was
already counted at ADD's own RETURN, so elaborating the single ticket ADD
just created and counted is the *same* wave, not a new one -- do NOT
increment again, or the valve double-counts one cycle (MAINTENANCE.md §2.4). Hits the 3-`goal_waves`/20-`goal_tickets` cap? STOP here
instead of continuing -- full BOARD/STATE checkpoint, report progress, wait
for the user to re-invoke `cc` to re-authorize and continue.